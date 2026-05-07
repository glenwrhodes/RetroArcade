"""A Space Invaders-style arcade game built with Tkinter."""

from __future__ import annotations

import random
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox


SCREEN_WIDTH = 860
SCREEN_HEIGHT = 640
TICK_MS = 16

PLAYER_WIDTH = 58
PLAYER_HEIGHT = 24
PLAYER_Y = SCREEN_HEIGHT - 64
PLAYER_SPEED = 6.5

BULLET_WIDTH = 5
BULLET_HEIGHT = 16
PLAYER_BULLET_SPEED = -10
ALIEN_BULLET_SPEED = 4.7

ALIEN_WIDTH = 42
ALIEN_HEIGHT = 28
ALIEN_X_GAP = 22
ALIEN_Y_GAP = 20
ALIEN_ROWS = 5
ALIEN_COLS = 10

BACKGROUND = "#020617"
STAR = "#e2e8f0"
PLAYER = "#22c55e"
PLAYER_DARK = "#15803d"
ALIEN_COLORS = ["#ef4444", "#f97316", "#eab308", "#38bdf8", "#a78bfa"]
BULLET = "#f8fafc"
ALIEN_BULLET = "#fb7185"
BARRIER = "#0f766e"
BARRIER_DAMAGED = "#facc15"
TEXT = "#f8fafc"
MUTED_TEXT = "#cbd5e1"
PANEL = "#0f172a"
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

    def intersects(self, other: "Rect") -> bool:
        return (
            self.left < other.right
            and self.right > other.left
            and self.top < other.bottom
            and self.bottom > other.top
        )


@dataclass
class Bullet(Rect):
    speed: float
    from_player: bool

    def update(self) -> None:
        self.y += self.speed


@dataclass
class Alien(Rect):
    row: int
    alive: bool = True


@dataclass
class BarrierBlock(Rect):
    health: int = 3


@dataclass
class PlayerShip:
    x: float = SCREEN_WIDTH / 2 - PLAYER_WIDTH / 2
    y: float = PLAYER_Y
    width: float = PLAYER_WIDTH
    height: float = PLAYER_HEIGHT
    lives: int = 3
    cooldown: int = 0
    invincible_ticks: int = 0

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.width, self.height)


class SpaceInvadersGame:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tkinter Space Invaders")
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
        self.player = PlayerShip()
        self.aliens: list[Alien] = []
        self.player_bullets: list[Bullet] = []
        self.alien_bullets: list[Bullet] = []
        self.barriers: list[BarrierBlock] = []
        self.stars: list[tuple[int, int, int]] = []
        self.alien_direction = 1
        self.alien_speed = 1.1
        self.alien_drop = 18
        self.score = 0
        self.level = 1
        self.game_over = False
        self.won_level_pause = 0
        self.after_id: str | None = None

        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.root.focus_set()

        self.restart()

    def restart(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.keys.clear()
        self.player = PlayerShip()
        self.player_bullets = []
        self.alien_bullets = []
        self.score = 0
        self.level = 1
        self.game_over = False
        self.won_level_pause = 0
        self.stars = [(random.randrange(SCREEN_WIDTH), random.randrange(SCREEN_HEIGHT), random.randrange(1, 3)) for _ in range(90)]
        self.create_barriers()
        self.create_alien_wave()
        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    def create_alien_wave(self) -> None:
        self.aliens = []
        total_width = ALIEN_COLS * ALIEN_WIDTH + (ALIEN_COLS - 1) * ALIEN_X_GAP
        start_x = (SCREEN_WIDTH - total_width) / 2
        start_y = 92

        for row in range(ALIEN_ROWS):
            for col in range(ALIEN_COLS):
                self.aliens.append(
                    Alien(
                        x=start_x + col * (ALIEN_WIDTH + ALIEN_X_GAP),
                        y=start_y + row * (ALIEN_HEIGHT + ALIEN_Y_GAP),
                        width=ALIEN_WIDTH,
                        height=ALIEN_HEIGHT,
                        row=row,
                    )
                )

        self.alien_direction = 1
        self.alien_speed = 1.0 + self.level * 0.18
        self.alien_drop = 18 + min(self.level, 8)
        self.player_bullets.clear()
        self.alien_bullets.clear()

    def create_barriers(self) -> None:
        self.barriers = []
        block_size = 14
        patterns = [
            "11111111",
            "11111111",
            "11100111",
            "11000011",
        ]

        for barrier_x in (130, 315, 500, 685):
            for row, pattern in enumerate(patterns):
                for col, value in enumerate(pattern):
                    if value == "1":
                        self.barriers.append(
                            BarrierBlock(
                                x=barrier_x + col * block_size,
                                y=430 + row * block_size,
                                width=block_size,
                                height=block_size,
                            )
                        )

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

        if not self.game_over:
            if self.won_level_pause > 0:
                self.won_level_pause -= 1
                if self.won_level_pause == 0:
                    self.level += 1
                    self.create_alien_wave()
            else:
                self.update_player()
                self.update_aliens()
                self.update_bullets()
                self.fire_alien_bullet()
                self.handle_collisions()
                self.check_level_state()

        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    def update_player(self) -> None:
        if self.player.cooldown > 0:
            self.player.cooldown -= 1
        if self.player.invincible_ticks > 0:
            self.player.invincible_ticks -= 1

        moving_left = "left" in self.keys or "a" in self.keys
        moving_right = "right" in self.keys or "d" in self.keys
        firing = "space" in self.keys or "up" in self.keys or "w" in self.keys

        if moving_left and not moving_right:
            self.player.x -= PLAYER_SPEED
        elif moving_right and not moving_left:
            self.player.x += PLAYER_SPEED

        self.player.x = max(16, min(self.player.x, SCREEN_WIDTH - self.player.width - 16))

        if firing and self.player.cooldown == 0:
            self.player_bullets.append(
                Bullet(
                    x=self.player.x + self.player.width / 2 - BULLET_WIDTH / 2,
                    y=self.player.y - BULLET_HEIGHT,
                    width=BULLET_WIDTH,
                    height=BULLET_HEIGHT,
                    speed=PLAYER_BULLET_SPEED,
                    from_player=True,
                )
            )
            self.player.cooldown = 18

    def update_aliens(self) -> None:
        living = [alien for alien in self.aliens if alien.alive]
        if not living:
            return

        speed_multiplier = 1 + (ALIEN_ROWS * ALIEN_COLS - len(living)) / 42
        dx = self.alien_direction * self.alien_speed * speed_multiplier
        should_drop = any((alien.right + dx >= SCREEN_WIDTH - 24) or (alien.left + dx <= 24) for alien in living)

        if should_drop:
            self.alien_direction *= -1
            for alien in living:
                alien.y += self.alien_drop
        else:
            for alien in living:
                alien.x += dx

        if any(alien.bottom >= self.player.y - 8 for alien in living):
            self.game_over = True

    def update_bullets(self) -> None:
        for bullet in self.player_bullets + self.alien_bullets:
            bullet.update()

        self.player_bullets = [bullet for bullet in self.player_bullets if bullet.bottom > 0]
        self.alien_bullets = [bullet for bullet in self.alien_bullets if bullet.top < SCREEN_HEIGHT]

    def fire_alien_bullet(self) -> None:
        living = [alien for alien in self.aliens if alien.alive]
        if not living:
            return

        chance = min(0.018 + self.level * 0.003, 0.045)
        if random.random() > chance:
            return

        bottom_aliens: dict[int, Alien] = {}
        for alien in living:
            col_key = round(alien.x / (ALIEN_WIDTH + ALIEN_X_GAP))
            if col_key not in bottom_aliens or alien.y > bottom_aliens[col_key].y:
                bottom_aliens[col_key] = alien

        shooter = random.choice(list(bottom_aliens.values()))
        self.alien_bullets.append(
            Bullet(
                x=shooter.x + shooter.width / 2 - BULLET_WIDTH / 2,
                y=shooter.bottom,
                width=BULLET_WIDTH,
                height=BULLET_HEIGHT,
                speed=ALIEN_BULLET_SPEED + self.level * 0.12,
                from_player=False,
            )
        )

    def handle_collisions(self) -> None:
        self.handle_player_bullet_hits()
        self.handle_alien_bullet_hits()
        self.remove_destroyed_barriers()

    def handle_player_bullet_hits(self) -> None:
        remaining_bullets: list[Bullet] = []

        for bullet in self.player_bullets:
            hit = False
            for alien in self.aliens:
                if alien.alive and bullet.intersects(alien):
                    alien.alive = False
                    self.score += (ALIEN_ROWS - alien.row) * 100
                    hit = True
                    break

            if hit:
                continue

            for barrier in self.barriers:
                if bullet.intersects(barrier):
                    barrier.health -= 1
                    hit = True
                    break

            if not hit:
                remaining_bullets.append(bullet)

        self.player_bullets = remaining_bullets

    def handle_alien_bullet_hits(self) -> None:
        remaining_bullets: list[Bullet] = []

        for bullet in self.alien_bullets:
            hit = False
            if bullet.intersects(self.player.rect):
                self.damage_player()
                hit = True

            if hit:
                continue

            for barrier in self.barriers:
                if bullet.intersects(barrier):
                    barrier.health -= 1
                    hit = True
                    break

            if not hit:
                remaining_bullets.append(bullet)

        self.alien_bullets = remaining_bullets

    def remove_destroyed_barriers(self) -> None:
        self.barriers = [barrier for barrier in self.barriers if barrier.health > 0]

    def damage_player(self) -> None:
        if self.player.invincible_ticks > 0:
            return

        self.player.lives -= 1
        self.alien_bullets.clear()
        self.player.invincible_ticks = 100
        if self.player.lives <= 0:
            self.game_over = True

    def check_level_state(self) -> None:
        if all(not alien.alive for alien in self.aliens):
            self.score += self.level * 500
            self.won_level_pause = 90

    def draw(self) -> None:
        self.canvas.delete("all")
        self.draw_background()
        self.draw_hud()
        self.draw_barriers()
        self.draw_player()
        self.draw_aliens()
        self.draw_bullets()

        if self.won_level_pause > 0 and not self.game_over:
            self.draw_center_banner("Wave Cleared", f"Get ready for level {self.level + 1}")
        elif self.game_over:
            self.draw_center_banner("Game Over", "Press R to restart")

    def draw_background(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, fill=BACKGROUND, outline="")
        for x, y, radius in self.stars:
            self.canvas.create_oval(x, y, x + radius, y + radius, fill=STAR, outline="")

        self.canvas.create_rectangle(0, SCREEN_HEIGHT - 34, SCREEN_WIDTH, SCREEN_HEIGHT, fill="#031712", outline="")
        for x in range(0, SCREEN_WIDTH, 36):
            self.canvas.create_line(x, SCREEN_HEIGHT - 34, x + 18, SCREEN_HEIGHT - 48, fill="#064e3b", width=2)

    def draw_hud(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, 52, fill=PANEL, outline="#1e293b")
        hud = f"Score: {self.score}    Lives: {self.player.lives}    Level: {self.level}"
        self.canvas.create_text(20, 26, text=hud, anchor="w", fill=TEXT, font=("Segoe UI", 14, "bold"))
        self.canvas.create_text(
            SCREEN_WIDTH - 20,
            26,
            text="Move: A/D or arrows   Fire: Space/Up/W   Restart: R",
            anchor="e",
            fill=MUTED_TEXT,
            font=("Segoe UI", 10),
        )

    def draw_player(self) -> None:
        if self.player.invincible_ticks and (self.player.invincible_ticks // 6) % 2 == 0:
            return

        x = self.player.x
        y = self.player.y
        self.canvas.create_polygon(
            x,
            y + PLAYER_HEIGHT,
            x + PLAYER_WIDTH / 2,
            y,
            x + PLAYER_WIDTH,
            y + PLAYER_HEIGHT,
            fill=PLAYER,
            outline=PLAYER_DARK,
            width=2,
        )
        self.canvas.create_rectangle(x + 10, y + 16, x + PLAYER_WIDTH - 10, y + PLAYER_HEIGHT + 6, fill=PLAYER_DARK, outline="")
        self.canvas.create_oval(x + 24, y + 7, x + 34, y + 17, fill="#bbf7d0", outline="")

    def draw_aliens(self) -> None:
        for alien in self.aliens:
            if not alien.alive:
                continue

            color = ALIEN_COLORS[alien.row % len(ALIEN_COLORS)]
            x = alien.x
            y = alien.y
            self.canvas.create_oval(x, y, x + alien.width, y + alien.height, fill=color, outline="#0f172a", width=2)
            self.canvas.create_rectangle(x + 6, y + 18, x + 14, y + 32, fill=color, outline="#0f172a")
            self.canvas.create_rectangle(x + alien.width - 14, y + 18, x + alien.width - 6, y + 32, fill=color, outline="#0f172a")
            self.canvas.create_oval(x + 10, y + 9, x + 16, y + 15, fill="#020617", outline="")
            self.canvas.create_oval(x + alien.width - 16, y + 9, x + alien.width - 10, y + 15, fill="#020617", outline="")

    def draw_bullets(self) -> None:
        for bullet in self.player_bullets:
            self.canvas.create_rectangle(
                bullet.x,
                bullet.y,
                bullet.x + bullet.width,
                bullet.y + bullet.height,
                fill=BULLET,
                outline="",
            )

        for bullet in self.alien_bullets:
            self.canvas.create_oval(
                bullet.x - 2,
                bullet.y,
                bullet.x + bullet.width + 2,
                bullet.y + bullet.height,
                fill=ALIEN_BULLET,
                outline="",
            )

    def draw_barriers(self) -> None:
        for barrier in self.barriers:
            color = BARRIER if barrier.health >= 2 else BARRIER_DAMAGED
            self.canvas.create_rectangle(
                barrier.x,
                barrier.y,
                barrier.x + barrier.width,
                barrier.y + barrier.height,
                fill=color,
                outline="#042f2e",
            )

    def draw_center_banner(self, title: str, subtitle: str) -> None:
        self.canvas.create_rectangle(245, 240, 615, 380, fill=PANEL, outline=ACCENT, width=3)
        self.canvas.create_text(430, 286, text=title, fill=TEXT, font=("Segoe UI", 28, "bold"))
        self.canvas.create_text(430, 330, text=subtitle, fill=MUTED_TEXT, font=("Segoe UI", 13))


def main() -> None:
    root = tk.Tk()
    try:
        root.iconname("Tkinter Space Invaders")
    except tk.TclError:
        pass

    SpaceInvadersGame(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except tk.TclError as exc:
        messagebox.showerror("Tkinter Space Invaders", f"Could not start Tkinter: {exc}")
