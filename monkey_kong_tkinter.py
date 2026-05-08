"""A ladder-climbing barrel dodger built with Tkinter."""

from __future__ import annotations

import random
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox


# The stage is a single-screen construction site with classic sloped girders.
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 640
HUD_HEIGHT = 54
TICK_MS = 16

GRAVITY = 0.72
PLAYER_SPEED = 4.8
JUMP_SPEED = -8.8
CLIMB_SPEED = 3.8
MAX_FALL_SPEED = 14
FRICTION = 0.8

BACKGROUND = "#0f172a"
SKY_GLOW = "#1e3a5f"
TEXT = "#f8fafc"
MUTED_TEXT = "#cbd5e1"
GIRDER = "#b91c1c"
GIRDER_EDGE = "#7f1d1d"
LADDER = "#f59e0b"
LADDER_EDGE = "#92400e"
PLAYER_SHIRT = "#0f766e"
PLAYER_PANTS = "#1d4ed8"
PLAYER_SKIN = "#fed7aa"
MONKEY = "#7c2d12"
MONKEY_FACE = "#d6a66a"
BARREL = "#92400e"
BARREL_BAND = "#fbbf24"
GOAL = "#facc15"
HEART = "#ef4444"


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
class Beam:
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float = 18

    def y_at(self, x: float) -> float:
        if self.x2 == self.x1:
            return self.y1
        t = (x - self.x1) / (self.x2 - self.x1)
        return self.y1 + (self.y2 - self.y1) * t

    @property
    def min_x(self) -> float:
        return min(self.x1, self.x2)

    @property
    def max_x(self) -> float:
        return max(self.x1, self.x2)

    @property
    def downhill_direction(self) -> int:
        return 1 if self.y2 > self.y1 else -1


@dataclass
class Ladder(Rect):
    pass


@dataclass
class Barrel:
    x: float
    y: float
    beam_index: int
    speed: float
    size: float = 28
    active: bool = True
    scored: bool = False
    spin: int = 0

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.size, self.size)


@dataclass
class Player:
    x: float = 78
    y: float = 548
    width: float = 30
    height: float = 46
    vx: float = 0
    vy: float = 0
    lives: int = 3
    invincible_ticks: int = 0
    climbing: bool = False
    on_ground: bool = False

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.width, self.height)


class MonkeyKongGame:
    """Runs the Monkey Kong stage, player physics, barrels, scoring, and drawing."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tkinter Monkey Kong")
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
        self.player = Player()
        self.beams: list[Beam] = []
        self.ladders: list[Ladder] = []
        self.barrels: list[Barrel] = []
        self.score = 0
        self.level = 1
        self.tick_count = 0
        self.spawn_timer = 0
        self.game_over = False
        self.victory = False
        self.after_id: str | None = None
        self.rng = random.Random(73)

        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.root.focus_set()

        self.restart()

    # Restart recreates every transient entity and cancels any previous scheduled loop.
    def restart(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.player = Player()
        self.barrels = []
        self.score = 0
        self.level = 1
        self.tick_count = 0
        self.spawn_timer = 45
        self.game_over = False
        self.victory = False
        self.keys.clear()
        self.build_stage()
        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    def build_stage(self) -> None:
        self.beams = [
            Beam(128, 168, 812, 206),
            Beam(90, 288, 790, 248),
            Beam(112, 358, 812, 398),
            Beam(88, 510, 792, 470),
            Beam(70, 596, 830, 596),
        ]

        self.ladders = [
            Ladder(700, 206, 48, 74),
            Ladder(160, 288, 48, 78),
            Ladder(642, 398, 48, 84),
            Ladder(260, 510, 48, 86),
            Ladder(738, 470, 48, 126),
        ]

    def on_key_press(self, event: tk.Event) -> None:
        key = self.normalized_key(event)
        self.keys.add(key)

        if key == "r":
            self.restart()
        elif key == "space":
            self.try_jump()

    def on_key_release(self, event: tk.Event) -> None:
        self.keys.discard(self.normalized_key(event))

    def normalized_key(self, event: tk.Event) -> str:
        key = event.keysym.lower()
        aliases = {
            "left": "left",
            "right": "right",
            "up": "up",
            "down": "down",
            "a": "left",
            "d": "right",
            "w": "up",
            "s": "down",
            "space": "space",
            "r": "r",
        }
        return aliases.get(key, key)

    def update(self) -> None:
        self.after_id = None
        if self.game_over or self.victory:
            self.draw()
            return

        self.tick_count += 1
        self.update_player()
        self.update_barrels()
        self.check_goal()
        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    def update_player(self) -> None:
        player = self.player
        previous_bottom = player.rect.bottom

        horizontal = 0
        if "left" in self.keys:
            horizontal -= 1
        if "right" in self.keys:
            horizontal += 1

        ladder = self.current_ladder()
        climb_direction = 0
        if "up" in self.keys:
            climb_direction -= 1
        if "down" in self.keys:
            climb_direction += 1

        if ladder is not None and climb_direction:
            player.climbing = True
            player.vx = horizontal * PLAYER_SPEED * 0.45
            player.vy = climb_direction * CLIMB_SPEED
            target_x = ladder.center_x - player.width / 2
            player.x += (target_x - player.x) * 0.18
        elif player.climbing and ladder is not None:
            player.vx = horizontal * PLAYER_SPEED * 0.45
            player.vy = 0
        else:
            player.climbing = False
            player.vx = horizontal * PLAYER_SPEED
            if horizontal == 0 and player.on_ground:
                player.vx *= FRICTION
            player.vy = min(player.vy + GRAVITY, MAX_FALL_SPEED)

        player.x += player.vx
        player.x = max(18, min(SCREEN_WIDTH - player.width - 18, player.x))
        player.y += player.vy
        player.on_ground = False

        if player.climbing:
            self.keep_player_inside_ladder(ladder)
            top_surface = self.ladder_surface(ladder, use_top=True)
            bottom_surface = self.ladder_surface(ladder, use_top=False)
            if climb_direction < 0 and top_surface is not None and player.rect.bottom <= top_surface + 4:
                self.land_player_on(top_surface)
                player.climbing = False
            elif climb_direction > 0 and bottom_surface is not None and player.rect.bottom >= bottom_surface - 4:
                self.land_player_on(bottom_surface)
                player.climbing = False
            return

        if player.vy >= 0:
            surface = self.first_surface_crossed(previous_bottom)
            if surface is not None:
                self.land_player_on(surface)

        if player.y > SCREEN_HEIGHT + 40:
            self.hurt_player()

        if player.invincible_ticks:
            player.invincible_ticks -= 1

    def keep_player_inside_ladder(self, ladder: Ladder | None) -> None:
        if ladder is None:
            self.player.climbing = False
            return

        top_surface = self.ladder_surface(ladder, use_top=True)
        bottom_surface = self.ladder_surface(ladder, use_top=False)
        top_limit = (top_surface if top_surface is not None else ladder.y) - self.player.height - 1
        bottom_limit = (bottom_surface if bottom_surface is not None else ladder.y + ladder.height) - self.player.height + 1
        self.player.y = max(top_limit, min(bottom_limit, self.player.y))

    def try_jump(self) -> None:
        if self.game_over or self.victory:
            return

        if self.player.climbing:
            self.player.climbing = False
            self.player.vy = JUMP_SPEED * 0.75
        elif self.player.on_ground:
            self.player.vy = JUMP_SPEED
            self.player.on_ground = False

    def current_ladder(self) -> Ladder | None:
        player_rect = self.player.rect
        for ladder in self.ladders:
            reach = Rect(ladder.x - 8, ladder.y - 8, ladder.width + 16, ladder.height + 18)
            if player_rect.intersects(reach):
                return ladder
        return None

    def first_surface_crossed(self, previous_bottom: float) -> float | None:
        player_rect = self.player.rect
        center_x = player_rect.center_x
        candidates: list[float] = []

        for beam in self.beams:
            if beam.min_x - 8 <= center_x <= beam.max_x + 8:
                surface_y = beam.y_at(center_x)
                if previous_bottom <= surface_y + 8 <= player_rect.bottom + 8:
                    candidates.append(surface_y)

        if not candidates:
            return None
        return min(candidates, key=lambda surface_y: abs(player_rect.bottom - surface_y))

    def surface_near_player(self) -> float | None:
        player_rect = self.player.rect
        center_x = player_rect.center_x
        for beam in self.beams:
            if beam.min_x - 10 <= center_x <= beam.max_x + 10:
                surface_y = beam.y_at(center_x)
                if abs(player_rect.bottom - surface_y) <= 12:
                    return surface_y
        return None

    def ladder_surface(self, ladder: Ladder | None, use_top: bool) -> float | None:
        if ladder is None:
            return None

        center_x = ladder.center_x
        reference_y = ladder.y if use_top else ladder.y + ladder.height
        surfaces = [
            beam.y_at(center_x)
            for beam in self.beams
            if beam.min_x - 10 <= center_x <= beam.max_x + 10
        ]
        if not surfaces:
            return None
        return min(surfaces, key=lambda surface_y: abs(surface_y - reference_y))

    def land_player_on(self, surface_y: float) -> None:
        self.player.y = surface_y - self.player.height
        self.player.vy = 0
        self.player.on_ground = True

    def update_barrels(self) -> None:
        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self.spawn_barrel()
            delay = max(74, 125 - self.level * 8)
            self.spawn_timer = delay + self.rng.randrange(0, 36)

        for barrel in self.barrels:
            if not barrel.active:
                continue

            beam = self.beams[barrel.beam_index]
            barrel.x += barrel.speed
            barrel.spin = (barrel.spin + 1) % 24

            if barrel.x < beam.min_x or barrel.x + barrel.size > beam.max_x:
                self.drop_barrel(barrel)
            else:
                barrel.y = beam.y_at(barrel.x + barrel.size / 2) - barrel.size

            if barrel.rect.intersects(self.player.rect):
                self.hurt_player()

            if not barrel.scored and self.player.vy < 0 and self.player.rect.bottom < barrel.rect.top:
                if abs(self.player.rect.center_x - barrel.rect.center_x) < 44:
                    barrel.scored = True
                    self.score += 100

        self.barrels = [barrel for barrel in self.barrels if barrel.active]

    def spawn_barrel(self) -> None:
        beam = self.beams[0]
        size = 28
        x = beam.min_x + 18
        speed = (2.2 + self.level * 0.18) * beam.downhill_direction
        self.barrels.append(Barrel(x, beam.y_at(x + size / 2) - size, 0, speed, size))

    def drop_barrel(self, barrel: Barrel) -> None:
        next_index = barrel.beam_index + 1
        if next_index >= len(self.beams):
            barrel.active = False
            self.score += 15
            return

        next_beam = self.beams[next_index]
        barrel.beam_index = next_index
        barrel.x = max(next_beam.min_x + 4, min(next_beam.max_x - barrel.size - 4, barrel.x))
        barrel.y = next_beam.y_at(barrel.x + barrel.size / 2) - barrel.size
        speed = 2.2 + self.level * 0.18
        barrel.speed = speed * next_beam.downhill_direction

    def hurt_player(self) -> None:
        if self.player.invincible_ticks:
            return

        self.player.lives -= 1
        if self.player.lives <= 0:
            self.game_over = True
            return

        lives = self.player.lives
        self.player = Player(lives=lives, invincible_ticks=95)
        self.barrels = []
        self.spawn_timer = 70

    def check_goal(self) -> None:
        goal_rect = Rect(424, 96, 72, 62)
        if self.player.rect.intersects(goal_rect):
            self.victory = True
            self.score += 1000 + self.player.lives * 250

    def draw(self) -> None:
        self.canvas.delete("all")
        self.draw_background()
        self.draw_stage()
        self.draw_goal()
        self.draw_monkey()
        self.draw_barrels()
        self.draw_player()
        self.draw_hud()

        if self.game_over:
            self.draw_center_banner("GAME OVER", "Press R to climb again")
        elif self.victory:
            self.draw_center_banner("NICE RESCUE!", "Press R for another run")

    def draw_background(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, fill=BACKGROUND, outline="")
        self.canvas.create_oval(610, 70, 980, 390, fill=SKY_GLOW, outline="")

        for x in range(44, SCREEN_WIDTH, 118):
            height = 70 + (x * 7) % 90
            self.canvas.create_rectangle(
                x,
                SCREEN_HEIGHT - height,
                x + 48,
                SCREEN_HEIGHT,
                fill="#111827",
                outline="#1f2937",
            )
            for window_y in range(SCREEN_HEIGHT - height + 14, SCREEN_HEIGHT - 12, 24):
                self.canvas.create_rectangle(x + 12, window_y, x + 20, window_y + 10, fill="#334155", outline="")
                self.canvas.create_rectangle(x + 29, window_y, x + 37, window_y + 10, fill="#334155", outline="")

    def draw_stage(self) -> None:
        for beam in self.beams:
            self.draw_beam(beam)

        for ladder in self.ladders:
            self.canvas.create_rectangle(
                ladder.x,
                ladder.y,
                ladder.x + ladder.width,
                ladder.y + ladder.height,
                fill="",
                outline="",
            )
            self.canvas.create_line(ladder.x + 10, ladder.y, ladder.x + 10, ladder.y + ladder.height, fill=LADDER_EDGE, width=5)
            self.canvas.create_line(
                ladder.x + ladder.width - 10,
                ladder.y,
                ladder.x + ladder.width - 10,
                ladder.y + ladder.height,
                fill=LADDER_EDGE,
                width=5,
            )
            rung_y = ladder.y + 8
            while rung_y < ladder.y + ladder.height:
                self.canvas.create_line(ladder.x + 9, rung_y, ladder.x + ladder.width - 9, rung_y, fill=LADDER, width=4)
                rung_y += 17

    def draw_beam(self, beam: Beam) -> None:
        self.canvas.create_line(
            beam.x1,
            beam.y1,
            beam.x2,
            beam.y2,
            fill=GIRDER_EDGE,
            width=int(beam.thickness + 8),
            capstyle=tk.ROUND,
        )
        self.canvas.create_line(
            beam.x1,
            beam.y1,
            beam.x2,
            beam.y2,
            fill=GIRDER,
            width=int(beam.thickness),
            capstyle=tk.ROUND,
        )

        span = beam.max_x - beam.min_x
        braces = max(5, int(span // 70))
        for brace in range(braces):
            t1 = brace / braces
            t2 = min(1, (brace + 0.55) / braces)
            x1 = beam.x1 + (beam.x2 - beam.x1) * t1
            y1 = beam.y1 + (beam.y2 - beam.y1) * t1
            x2 = beam.x1 + (beam.x2 - beam.x1) * t2
            y2 = beam.y1 + (beam.y2 - beam.y1) * t2
            self.canvas.create_line(x1, y1 - 9, x2, y2 + 9, fill="#fecaca", width=2)

    def draw_goal(self) -> None:
        self.canvas.create_rectangle(382, 72, 538, 160, fill="#172554", outline="#38bdf8", width=3)
        self.canvas.create_text(460, 93, text="HELP!", fill=TEXT, font=("Segoe UI", 13, "bold"))
        self.canvas.create_oval(433, 105, 487, 158, fill=PLAYER_SKIN, outline="#9a3412", width=2)
        self.canvas.create_rectangle(446, 135, 474, 163, fill=GOAL, outline="#ca8a04", width=2)
        self.canvas.create_oval(445, 116, 454, 125, fill="#111827", outline="")
        self.canvas.create_oval(466, 116, 475, 125, fill="#111827", outline="")

    def draw_monkey(self) -> None:
        self.canvas.create_oval(138, 78, 226, 156, fill=MONKEY, outline="#451a03", width=3)
        self.canvas.create_oval(158, 94, 206, 140, fill=MONKEY_FACE, outline="#78350f", width=2)
        self.canvas.create_oval(146, 86, 172, 112, fill=MONKEY, outline="#451a03", width=2)
        self.canvas.create_oval(192, 86, 218, 112, fill=MONKEY, outline="#451a03", width=2)
        self.canvas.create_oval(171, 109, 179, 117, fill="#111827", outline="")
        self.canvas.create_oval(188, 109, 196, 117, fill="#111827", outline="")
        self.canvas.create_arc(174, 118, 196, 135, start=200, extent=140, outline="#451a03", width=3, style=tk.ARC)
        self.canvas.create_rectangle(120, 138, 244, 166, fill=MONKEY, outline="#451a03", width=3)
        self.canvas.create_text(184, 184, text="MONKEY KONG", fill=TEXT, font=("Segoe UI", 11, "bold"))

    def draw_barrels(self) -> None:
        for barrel in self.barrels:
            rect = barrel.rect
            self.canvas.create_oval(rect.x, rect.y, rect.right, rect.bottom, fill=BARREL, outline="#451a03", width=3)
            self.canvas.create_line(rect.x + 6, rect.y + 5, rect.right - 6, rect.bottom - 5, fill=BARREL_BAND, width=3)
            self.canvas.create_line(rect.x + 6, rect.bottom - 5, rect.right - 6, rect.y + 5, fill=BARREL_BAND, width=3)
            if barrel.spin < 12:
                self.canvas.create_line(rect.center_x, rect.y + 3, rect.center_x, rect.bottom - 3, fill="#fed7aa", width=2)
            else:
                self.canvas.create_line(rect.x + 3, rect.center_y, rect.right - 3, rect.center_y, fill="#fed7aa", width=2)

    def draw_player(self) -> None:
        if self.player.invincible_ticks and (self.player.invincible_ticks // 5) % 2 == 0:
            return

        x = self.player.x
        y = self.player.y
        self.canvas.create_rectangle(x + 5, y + 22, x + 25, y + 45, fill=PLAYER_PANTS, outline="#1e3a8a", width=2)
        self.canvas.create_rectangle(x + 3, y + 16, x + 27, y + 31, fill=PLAYER_SHIRT, outline="#134e4a", width=2)
        self.canvas.create_oval(x + 5, y, x + 25, y + 21, fill=PLAYER_SKIN, outline="#9a3412", width=2)
        self.canvas.create_rectangle(x + 2, y - 3, x + 28, y + 7, fill="#b45309", outline="#78350f", width=2)
        self.canvas.create_oval(x + 17, y + 9, x + 22, y + 14, fill="#111827", outline="")
        self.canvas.create_rectangle(x + 1, y + 42, x + 12, y + 49, fill="#451a03", outline="")
        self.canvas.create_rectangle(x + 18, y + 42, x + 29, y + 49, fill="#451a03", outline="")

    def draw_hud(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, HUD_HEIGHT, fill="#020617", outline="#334155")
        self.canvas.create_text(
            18,
            26,
            text=f"Score: {self.score}    Level: {self.level}",
            anchor="w",
            fill=TEXT,
            font=("Segoe UI", 14, "bold"),
        )

        for life in range(self.player.lives):
            x = 232 + life * 24
            self.canvas.create_oval(x, 18, x + 13, 31, fill=HEART, outline="")
            self.canvas.create_oval(x + 9, 18, x + 22, 31, fill=HEART, outline="")
            self.canvas.create_polygon(x - 1, 25, x + 23, 25, x + 11, 39, fill=HEART, outline="")

        self.canvas.create_text(
            SCREEN_WIDTH - 18,
            26,
            text="Move: A/D or arrows   Climb: W/S or Up/Down   Jump: Space   Restart: R",
            anchor="e",
            fill=MUTED_TEXT,
            font=("Segoe UI", 10),
        )

    def draw_center_banner(self, title: str, subtitle: str) -> None:
        self.canvas.create_rectangle(258, 246, 642, 384, fill="#0f172a", outline="#38bdf8", width=3)
        self.canvas.create_text(450, 292, text=title, fill=TEXT, font=("Segoe UI", 28, "bold"))
        self.canvas.create_text(450, 335, text=subtitle, fill=MUTED_TEXT, font=("Segoe UI", 13))


def main() -> None:
    """Create the Tkinter root and hand control to Tkinter's event loop."""
    root = tk.Tk()
    try:
        root.iconname("Tkinter Monkey Kong")
    except tk.TclError:
        pass

    MonkeyKongGame(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except tk.TclError as exc:
        messagebox.showerror("Tkinter Monkey Kong", f"Could not start Tkinter: {exc}")
