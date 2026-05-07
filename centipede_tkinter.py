"""A Centipede-style arcade shooter built with Tkinter."""

from __future__ import annotations

import random
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox


SCREEN_WIDTH = 760
SCREEN_HEIGHT = 720
TICK_MS = 16

CELL_SIZE = 24
GRID_COLS = SCREEN_WIDTH // CELL_SIZE
GRID_ROWS = SCREEN_HEIGHT // CELL_SIZE
HUD_HEIGHT = 48
PLAYER_ZONE_TOP = SCREEN_HEIGHT - 150

PLAYER_WIDTH = 34
PLAYER_HEIGHT = 28
PLAYER_SPEED = 6.0
BULLET_WIDTH = 5
BULLET_HEIGHT = 16
BULLET_SPEED = -12

BACKGROUND = "#06121f"
HUD = "#0f172a"
TEXT = "#f8fafc"
MUTED = "#cbd5e1"
PLAYER = "#38bdf8"
PLAYER_DARK = "#075985"
SHOT = "#f8fafc"
MUSHROOM = "#ec4899"
MUSHROOM_DARK = "#9d174d"
CENTIPEDE = "#84cc16"
CENTIPEDE_HEAD = "#facc15"
CENTIPEDE_DARK = "#365314"
SPIDER = "#f97316"
FLEA = "#a78bfa"
ACCENT = "#14b8a6"


@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    def intersects(self, other: "Rect") -> bool:
        return (
            self.left < other.right
            and self.right > other.left
            and self.top < other.bottom
            and self.bottom > other.top
        )


@dataclass
class Mushroom:
    col: int
    row: int
    health: int = 4

    @property
    def rect(self) -> Rect:
        return Rect(self.col * CELL_SIZE + 3, self.row * CELL_SIZE + 3, CELL_SIZE - 6, CELL_SIZE - 6)


@dataclass
class Bullet(Rect):
    active: bool = True

    def update(self) -> None:
        self.y += BULLET_SPEED
        if self.bottom < HUD_HEIGHT:
            self.active = False


@dataclass
class Player(Rect):
    lives: int = 3
    cooldown: int = 0
    invincible_ticks: int = 0


@dataclass
class Segment(Rect):
    direction: int
    row: int
    col: int
    is_head: bool = False

    def sync_position(self) -> None:
        self.x = self.col * CELL_SIZE
        self.y = self.row * CELL_SIZE


@dataclass
class Spider(Rect):
    vx: float
    vy: float
    active: bool = True


@dataclass
class Flea(Rect):
    vy: float = 4.0
    active: bool = True


class CentipedeGame:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tkinter Centipede")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            root,
            width=SCREEN_WIDTH,
            height=SCREEN_HEIGHT,
            bg=BACKGROUND,
            highlightthickness=0,
        )
        self.canvas.pack()

        self.keys: set[str] = set()
        self.player = Player(SCREEN_WIDTH / 2 - PLAYER_WIDTH / 2, SCREEN_HEIGHT - 54, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.bullet: Bullet | None = None
        self.mushrooms: dict[tuple[int, int], Mushroom] = {}
        self.segments: list[Segment] = []
        self.spider: Spider | None = None
        self.flea: Flea | None = None
        self.score = 0
        self.wave = 1
        self.game_over = False
        self.tick_count = 0
        self.after_id: str | None = None
        self.rng = random.Random(42)

        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.root.focus_set()

        self.restart()

    def restart(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.keys.clear()
        self.player = Player(SCREEN_WIDTH / 2 - PLAYER_WIDTH / 2, SCREEN_HEIGHT - 54, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.bullet = None
        self.score = 0
        self.wave = 1
        self.game_over = False
        self.tick_count = 0
        self.rng = random.Random(42)
        self.create_mushroom_field()
        self.spawn_centipede()
        self.spider = None
        self.flea = None
        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    def create_mushroom_field(self) -> None:
        self.mushrooms = {}
        for _ in range(58):
            col = self.rng.randrange(1, GRID_COLS - 1)
            row = self.rng.randrange(3, GRID_ROWS - 6)
            self.mushrooms[(col, row)] = Mushroom(col, row)

    def spawn_centipede(self) -> None:
        self.segments = []
        length = 10 + min(self.wave, 8)
        for index in range(length):
            col = max(0, min(GRID_COLS - 1, index))
            segment = Segment(
                x=col * CELL_SIZE,
                y=HUD_HEIGHT,
                width=CELL_SIZE,
                height=CELL_SIZE,
                direction=1,
                row=HUD_HEIGHT // CELL_SIZE,
                col=col,
                is_head=index == length - 1,
            )
            self.segments.append(segment)

    def on_key_press(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        if key == "r":
            self.restart()
            return
        self.keys.add(key)

    def on_key_release(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym.lower())

    def update(self) -> None:
        self.after_id = None
        self.tick_count += 1

        if not self.game_over:
            self.update_player()
            self.update_bullet()
            self.update_centipede()
            self.update_spider()
            self.update_flea()
            self.handle_collisions()
            self.maybe_spawn_side_enemies()
            self.check_wave_clear()

        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    def update_player(self) -> None:
        if self.player.cooldown > 0:
            self.player.cooldown -= 1
        if self.player.invincible_ticks > 0:
            self.player.invincible_ticks -= 1

        dx = 0.0
        dy = 0.0
        if "left" in self.keys or "a" in self.keys:
            dx -= PLAYER_SPEED
        if "right" in self.keys or "d" in self.keys:
            dx += PLAYER_SPEED
        if "up" in self.keys or "w" in self.keys:
            dy -= PLAYER_SPEED
        if "down" in self.keys or "s" in self.keys:
            dy += PLAYER_SPEED

        self.player.x = max(0, min(self.player.x + dx, SCREEN_WIDTH - self.player.width))
        self.player.y = max(PLAYER_ZONE_TOP, min(self.player.y + dy, SCREEN_HEIGHT - self.player.height - 8))

        firing = "space" in self.keys or "z" in self.keys or "up" in self.keys
        if firing and self.bullet is None and self.player.cooldown == 0:
            self.bullet = Bullet(
                self.player.center_x - BULLET_WIDTH / 2,
                self.player.y - BULLET_HEIGHT,
                BULLET_WIDTH,
                BULLET_HEIGHT,
            )
            self.player.cooldown = 8

    def update_bullet(self) -> None:
        if self.bullet is None:
            return
        self.bullet.update()
        if not self.bullet.active:
            self.bullet = None

    def update_centipede(self) -> None:
        if self.tick_count % max(3, 10 - self.wave) != 0:
            return

        occupied_mushrooms = set(self.mushrooms)
        for segment in self.segments:
            next_col = segment.col + segment.direction
            blocked = (
                next_col < 0
                or next_col >= GRID_COLS
                or (next_col, segment.row) in occupied_mushrooms
            )
            if blocked:
                segment.direction *= -1
                segment.row += 1
                if segment.row >= GRID_ROWS:
                    segment.row = PLAYER_ZONE_TOP // CELL_SIZE
            else:
                segment.col = next_col
            segment.sync_position()

    def update_spider(self) -> None:
        if self.spider is None or not self.spider.active:
            self.spider = None
            return

        self.spider.x += self.spider.vx
        self.spider.y += self.spider.vy
        if self.rng.random() < 0.03:
            self.spider.vy *= -1
        if self.spider.y < PLAYER_ZONE_TOP:
            self.spider.y = PLAYER_ZONE_TOP
            self.spider.vy = abs(self.spider.vy)
        elif self.spider.bottom > SCREEN_HEIGHT - 12:
            self.spider.y = SCREEN_HEIGHT - 12 - self.spider.height
            self.spider.vy = -abs(self.spider.vy)
        if self.spider.right < -40 or self.spider.left > SCREEN_WIDTH + 40:
            self.spider.active = False

    def update_flea(self) -> None:
        if self.flea is None or not self.flea.active:
            self.flea = None
            return

        self.flea.y += self.flea.vy
        if self.tick_count % 8 == 0:
            col = int(self.flea.center_x // CELL_SIZE)
            row = int(self.flea.center_y // CELL_SIZE)
            if 3 <= row < GRID_ROWS - 5 and (col, row) not in self.mushrooms:
                self.mushrooms[(col, row)] = Mushroom(col, row)
        if self.flea.top > SCREEN_HEIGHT:
            self.flea.active = False

    def maybe_spawn_side_enemies(self) -> None:
        if self.spider is None and self.rng.random() < 0.004 + self.wave * 0.0005:
            from_left = self.rng.choice((True, False))
            x = -34 if from_left else SCREEN_WIDTH + 34
            vx = self.rng.uniform(2.5, 4.0) * (1 if from_left else -1)
            vy = self.rng.choice((-1.8, 1.8))
            self.spider = Spider(x, self.rng.randrange(int(PLAYER_ZONE_TOP), SCREEN_HEIGHT - 60), 34, 26, vx, vy)

        if self.flea is None and len([m for m in self.mushrooms.values() if m.row >= PLAYER_ZONE_TOP // CELL_SIZE]) < 6:
            if self.rng.random() < 0.01:
                x = self.rng.randrange(2, GRID_COLS - 2) * CELL_SIZE + 4
                self.flea = Flea(x, HUD_HEIGHT, 16, 28)

    def handle_collisions(self) -> None:
        if self.bullet is not None:
            self.handle_bullet_collisions()

        if self.player.invincible_ticks > 0:
            return

        player_hit = any(segment.intersects(self.player) for segment in self.segments)
        if self.spider is not None and self.spider.intersects(self.player):
            player_hit = True
        if self.flea is not None and self.flea.intersects(self.player):
            player_hit = True

        if player_hit:
            self.damage_player()

    def handle_bullet_collisions(self) -> None:
        if self.bullet is None:
            return

        bullet = self.bullet
        for key, mushroom in list(self.mushrooms.items()):
            if bullet.intersects(mushroom.rect):
                mushroom.health -= 1
                self.score += 1
                if mushroom.health <= 0:
                    del self.mushrooms[key]
                    self.score += 4
                self.bullet = None
                return

        for segment in list(self.segments):
            if bullet.intersects(segment):
                self.score += 100 if segment.is_head else 50
                col = int(segment.center_x // CELL_SIZE)
                row = int(segment.center_y // CELL_SIZE)
                self.mushrooms[(col, row)] = Mushroom(col, row, health=4)
                self.split_centipede_at(segment)
                self.bullet = None
                return

        if self.spider is not None and bullet.intersects(self.spider):
            distance = abs(self.player.center_y - self.spider.center_y)
            self.score += 900 if distance < 60 else 600 if distance < 110 else 300
            self.spider.active = False
            self.bullet = None
            return

        if self.flea is not None and bullet.intersects(self.flea):
            self.score += 200
            self.flea.active = False
            self.bullet = None

    def split_centipede_at(self, hit_segment: Segment) -> None:
        hit_index = self.segments.index(hit_segment)
        del self.segments[hit_index]
        for index, segment in enumerate(self.segments):
            segment.is_head = index == len(self.segments) - 1 or index == hit_index

    def damage_player(self) -> None:
        self.player.lives -= 1
        if self.player.lives <= 0:
            self.game_over = True
            return

        self.player.x = SCREEN_WIDTH / 2 - PLAYER_WIDTH / 2
        self.player.y = SCREEN_HEIGHT - 54
        self.player.invincible_ticks = 120
        self.bullet = None

    def check_wave_clear(self) -> None:
        if self.segments:
            return
        self.wave += 1
        self.score += 1000
        self.spawn_centipede()

    def draw(self) -> None:
        self.canvas.delete("all")
        self.draw_background()
        self.draw_mushrooms()
        self.draw_centipede()
        self.draw_side_enemies()
        self.draw_bullet()
        self.draw_player()
        self.draw_hud()

        if self.game_over:
            self.draw_center_banner("Game Over", "Press R to restart")

    def draw_background(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, fill=BACKGROUND, outline="")
        self.canvas.create_rectangle(0, PLAYER_ZONE_TOP, SCREEN_WIDTH, SCREEN_HEIGHT, fill="#081827", outline="")
        for x in range(0, SCREEN_WIDTH, CELL_SIZE):
            self.canvas.create_line(x, PLAYER_ZONE_TOP, x, SCREEN_HEIGHT, fill="#0f2538")

    def draw_hud(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, HUD_HEIGHT, fill=HUD, outline="#1e293b")
        self.canvas.create_text(
            18,
            24,
            text=f"Score: {self.score}    Lives: {self.player.lives}    Wave: {self.wave}",
            anchor="w",
            fill=TEXT,
            font=("Segoe UI", 14, "bold"),
        )
        self.canvas.create_text(
            SCREEN_WIDTH - 18,
            24,
            text="Move: WASD/arrows   Fire: Space/Z/Up   Restart: R",
            anchor="e",
            fill=MUTED,
            font=("Segoe UI", 10),
        )

    def draw_mushrooms(self) -> None:
        for mushroom in self.mushrooms.values():
            rect = mushroom.rect
            color = MUSHROOM if mushroom.health >= 3 else "#f472b6" if mushroom.health == 2 else "#f9a8d4"
            self.canvas.create_oval(rect.x, rect.y + 5, rect.x + rect.width, rect.y + rect.height, fill=color, outline=MUSHROOM_DARK, width=2)
            self.canvas.create_rectangle(rect.x + 7, rect.y + 14, rect.x + rect.width - 7, rect.y + rect.height + 3, fill="#f8fafc", outline=MUSHROOM_DARK)
            for dot_x in (rect.x + 7, rect.x + rect.width - 9):
                self.canvas.create_oval(dot_x, rect.y + 9, dot_x + 4, rect.y + 13, fill="#fdf2f8", outline="")

    def draw_centipede(self) -> None:
        for segment in self.segments:
            x = segment.x + 2
            y = segment.y + 2
            color = CENTIPEDE_HEAD if segment.is_head else CENTIPEDE
            self.canvas.create_oval(x, y, x + CELL_SIZE - 4, y + CELL_SIZE - 4, fill=color, outline=CENTIPEDE_DARK, width=2)
            self.canvas.create_oval(x + 6, y + 7, x + 10, y + 11, fill="#020617", outline="")
            self.canvas.create_oval(x + 14, y + 7, x + 18, y + 11, fill="#020617", outline="")

    def draw_player(self) -> None:
        if self.player.invincible_ticks and (self.player.invincible_ticks // 6) % 2 == 0:
            return
        x = self.player.x
        y = self.player.y
        self.canvas.create_polygon(
            x + PLAYER_WIDTH / 2,
            y,
            x + PLAYER_WIDTH,
            y + PLAYER_HEIGHT,
            x + PLAYER_WIDTH / 2,
            y + PLAYER_HEIGHT - 8,
            x,
            y + PLAYER_HEIGHT,
            fill=PLAYER,
            outline=PLAYER_DARK,
            width=2,
        )
        self.canvas.create_oval(x + 11, y + 10, x + 23, y + 21, fill="#e0f2fe", outline=PLAYER_DARK)

    def draw_bullet(self) -> None:
        if self.bullet is None:
            return
        self.canvas.create_rectangle(
            self.bullet.x,
            self.bullet.y,
            self.bullet.x + self.bullet.width,
            self.bullet.y + self.bullet.height,
            fill=SHOT,
            outline="",
        )

    def draw_side_enemies(self) -> None:
        if self.spider is not None:
            x = self.spider.x
            y = self.spider.y
            self.canvas.create_oval(x, y, x + self.spider.width, y + self.spider.height, fill=SPIDER, outline="#9a3412", width=2)
            for leg in range(4):
                ly = y + 6 + leg * 4
                self.canvas.create_line(x + 4, ly, x - 8, ly + 5, fill=SPIDER, width=2)
                self.canvas.create_line(x + self.spider.width - 4, ly, x + self.spider.width + 8, ly + 5, fill=SPIDER, width=2)
            self.canvas.create_oval(x + 9, y + 8, x + 14, y + 13, fill="#020617", outline="")
            self.canvas.create_oval(x + 21, y + 8, x + 26, y + 13, fill="#020617", outline="")

        if self.flea is not None:
            x = self.flea.x
            y = self.flea.y
            self.canvas.create_oval(x, y, x + self.flea.width, y + self.flea.height, fill=FLEA, outline="#5b21b6", width=2)
            self.canvas.create_line(x + 4, y + 8, x - 6, y + 2, fill=FLEA, width=2)
            self.canvas.create_line(x + self.flea.width - 4, y + 8, x + self.flea.width + 6, y + 2, fill=FLEA, width=2)

    def draw_center_banner(self, title: str, subtitle: str) -> None:
        self.canvas.create_rectangle(205, 285, 555, 410, fill=HUD, outline=ACCENT, width=3)
        self.canvas.create_text(SCREEN_WIDTH / 2, 326, text=title, fill=TEXT, font=("Segoe UI", 27, "bold"))
        self.canvas.create_text(SCREEN_WIDTH / 2, 366, text=subtitle, fill=MUTED, font=("Segoe UI", 13))


def main() -> None:
    root = tk.Tk()
    try:
        root.iconname("Tkinter Centipede")
    except tk.TclError:
        pass

    CentipedeGame(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except tk.TclError as exc:
        messagebox.showerror("Tkinter Centipede", f"Could not start Tkinter: {exc}")
