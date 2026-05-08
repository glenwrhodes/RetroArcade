"""A small side-scrolling platform runner built with Tkinter."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox


# World dimensions, physics tuning, and frame timing define the feel of the platformer.
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 540
GROUND_Y = 470
WORLD_WIDTH = 3100
TICK_MS = 16

GRAVITY = 0.75
MOVE_SPEED = 5.2
JUMP_SPEED = -15.5
MAX_FALL_SPEED = 18
FRICTION = 0.78

SKY = "#87ceeb"
GROUND = "#15803d"
DIRT = "#92400e"
BRICK = "#b45309"
BRICK_EDGE = "#7c2d12"
CLOUD = "#f8fafc"
TEXT = "#0f172a"
PLAYER_RED = "#dc2626"
PLAYER_BLUE = "#2563eb"
PLAYER_SKIN = "#fed7aa"
ENEMY = "#78350f"
COIN = "#facc15"
FLAG = "#0f766e"


# Shared rectangle math keeps movement, collision, and drawing code using one geometry model.
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
class Platform(Rect):
    color: str = BRICK


@dataclass
class Coin:
    x: float
    y: float
    collected: bool = False

    @property
    def rect(self) -> Rect:
        return Rect(self.x - 12, self.y - 12, 24, 24)


@dataclass
class Enemy:
    x: float
    y: float
    left_bound: float
    right_bound: float
    speed: float = 1.6
    width: float = 34
    height: float = 30
    alive: bool = True

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.width, self.height)

    def update(self) -> None:
        if not self.alive:
            return

        self.x += self.speed
        if self.x <= self.left_bound or self.x + self.width >= self.right_bound:
            self.speed *= -1
            self.x = max(self.left_bound, min(self.x, self.right_bound - self.width))


@dataclass
class Player:
    x: float = 80
    y: float = GROUND_Y - 54
    width: float = 34
    height: float = 54
    vx: float = 0
    vy: float = 0
    on_ground: bool = False
    lives: int = 3
    invincible_ticks: int = 0

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.width, self.height)


class PixelRunnerTkinterGame:
    """Coordinates the level data, input state, physics loop, camera, and canvas drawing."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tkinter Pixel Runner")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            root,
            width=SCREEN_WIDTH,
            height=SCREEN_HEIGHT,
            bg=SKY,
            highlightthickness=0,
        )
        self.canvas.pack()

        self.keys: set[str] = set()
        self.player = Player()
        self.platforms: list[Platform] = []
        self.coins: list[Coin] = []
        self.enemies: list[Enemy] = []
        self.camera_x = 0.0
        self.score = 0
        self.finished = False
        self.game_over = False
        self.after_id: str | None = None

        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.root.focus_set()

        self.restart()

    # Restart rebuilds all transient game state and cancels any old scheduled frame.
    def restart(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.player = Player()
        self.camera_x = 0.0
        self.score = 0
        self.finished = False
        self.game_over = False
        self.keys.clear()
        self.build_level()
        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    # The level is hard-coded as simple entity lists so the game stays self-contained.
    def build_level(self) -> None:
        self.platforms = [
            Platform(0, GROUND_Y, WORLD_WIDTH, SCREEN_HEIGHT - GROUND_Y, GROUND),
            Platform(260, 390, 150, 28),
            Platform(500, 330, 150, 28),
            Platform(760, 385, 180, 28),
            Platform(1060, 315, 160, 28),
            Platform(1320, 395, 220, 28),
            Platform(1660, 340, 160, 28),
            Platform(1900, 280, 180, 28),
            Platform(2210, 365, 190, 28),
            Platform(2500, 315, 160, 28),
            Platform(2750, 405, 130, 28),
        ]

        self.coins = [
            Coin(320, 350),
            Coin(560, 290),
            Coin(820, 345),
            Coin(890, 345),
            Coin(1130, 275),
            Coin(1410, 355),
            Coin(1490, 355),
            Coin(1725, 300),
            Coin(1980, 240),
            Coin(2290, 325),
            Coin(2565, 275),
            Coin(2815, 365),
        ]

        self.enemies = [
            Enemy(640, GROUND_Y - 30, 610, 900),
            Enemy(1240, GROUND_Y - 30, 1220, 1520, -1.7),
            Enemy(1770, GROUND_Y - 30, 1700, 2040),
            Enemy(2230, 335, 2210, 2400, -1.4),
        ]

    # Input is stored as pressed keys; the update loop translates it into movement.
    def on_key_press(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        if key == "r":
            self.restart()
            return
        self.keys.add(key)

    def on_key_release(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym.lower())

    # One frame of gameplay: apply physics, move actors, resolve interactions, then redraw.
    def update(self) -> None:
        self.after_id = None
        if not self.game_over and not self.finished:
            self.update_player()
            self.update_enemies()
            self.collect_coins()
            self.check_enemy_collisions()
            self.check_goal()
            self.update_camera()

        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    # Horizontal and vertical movement are split so platform collision can be resolved cleanly.
    def update_player(self) -> None:
        if self.player.invincible_ticks > 0:
            self.player.invincible_ticks -= 1

        moving_left = "left" in self.keys or "a" in self.keys
        moving_right = "right" in self.keys or "d" in self.keys
        wants_jump = "space" in self.keys or "up" in self.keys or "w" in self.keys

        if moving_left and not moving_right:
            self.player.vx = -MOVE_SPEED
        elif moving_right and not moving_left:
            self.player.vx = MOVE_SPEED
        else:
            self.player.vx *= FRICTION
            if abs(self.player.vx) < 0.15:
                self.player.vx = 0

        if wants_jump and self.player.on_ground:
            self.player.vy = JUMP_SPEED
            self.player.on_ground = False

        self.player.vy = min(self.player.vy + GRAVITY, MAX_FALL_SPEED)
        self.move_player_horizontally()
        self.move_player_vertically()

        if self.player.y > SCREEN_HEIGHT + 120:
            self.hurt_player()

    # Platform collisions are handled separately on each axis to avoid corner tunneling.
    def move_player_horizontally(self) -> None:
        self.player.x += self.player.vx
        self.player.x = max(0, min(self.player.x, WORLD_WIDTH - self.player.width))

        for platform in self.platforms:
            if self.player.rect.intersects(platform):
                if self.player.vx > 0:
                    self.player.x = platform.left - self.player.width
                elif self.player.vx < 0:
                    self.player.x = platform.right
                self.player.vx = 0

    def move_player_vertically(self) -> None:
        self.player.y += self.player.vy
        self.player.on_ground = False

        for platform in self.platforms:
            if self.player.rect.intersects(platform):
                if self.player.vy > 0:
                    self.player.y = platform.top - self.player.height
                    self.player.vy = 0
                    self.player.on_ground = True
                elif self.player.vy < 0:
                    self.player.y = platform.bottom
                    self.player.vy = 0

    # Interaction checks handle enemy movement, pickups, player damage, and reaching the flag.
    def update_enemies(self) -> None:
        for enemy in self.enemies:
            enemy.update()

    def collect_coins(self) -> None:
        for coin in self.coins:
            if not coin.collected and self.player.rect.intersects(coin.rect):
                coin.collected = True
                self.score += 100

    def check_enemy_collisions(self) -> None:
        for enemy in self.enemies:
            if not enemy.alive or not self.player.rect.intersects(enemy.rect):
                continue

            player_was_falling = self.player.vy > 0
            player_bottom = self.player.rect.bottom
            enemy_top = enemy.rect.top
            if player_was_falling and player_bottom - enemy_top < 24:
                enemy.alive = False
                self.player.vy = JUMP_SPEED * 0.55
                self.score += 250
            else:
                self.hurt_player()

    def hurt_player(self) -> None:
        if self.player.invincible_ticks > 0:
            return

        self.player.lives -= 1
        if self.player.lives <= 0:
            self.game_over = True
            return

        checkpoint = max(80, self.camera_x + 80)
        self.player.x = checkpoint
        self.player.y = GROUND_Y - self.player.height
        self.player.vx = 0
        self.player.vy = 0
        self.player.invincible_ticks = 110

    def check_goal(self) -> None:
        if self.player.x + self.player.width >= WORLD_WIDTH - 155:
            self.finished = True
            self.score += 1000 + self.player.lives * 500

    def update_camera(self) -> None:
        target = self.player.x - SCREEN_WIDTH * 0.38
        self.camera_x += (target - self.camera_x) * 0.12
        self.camera_x = max(0, min(self.camera_x, WORLD_WIDTH - SCREEN_WIDTH))

    # Drawing converts world coordinates through the camera and rebuilds the canvas each frame.
    def draw(self) -> None:
        self.canvas.delete("all")
        self.draw_sky()
        self.draw_platforms()
        self.draw_coins()
        self.draw_enemies()
        self.draw_goal()
        self.draw_player()
        self.draw_hud()

        if self.finished:
            self.draw_center_banner("You Win!", "Press R to play again")
        elif self.game_over:
            self.draw_center_banner("Game Over", "Press R to restart")

    def world_to_screen(self, x: float, y: float) -> tuple[float, float]:
        return x - self.camera_x, y

    def draw_sky(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, fill=SKY, outline="")

        for cloud_x, cloud_y in [(160, 85), (520, 130), (940, 70), (1470, 120), (2140, 85), (2700, 140)]:
            sx, sy = self.world_to_screen(cloud_x, cloud_y)
            if -120 <= sx <= SCREEN_WIDTH + 120:
                self.canvas.create_oval(sx, sy, sx + 70, sy + 34, fill=CLOUD, outline="")
                self.canvas.create_oval(sx + 35, sy - 14, sx + 105, sy + 34, fill=CLOUD, outline="")
                self.canvas.create_oval(sx + 75, sy + 2, sx + 135, sy + 34, fill=CLOUD, outline="")

        for hill_x in (120, 780, 1420, 2070, 2660):
            sx, _ = self.world_to_screen(hill_x, GROUND_Y)
            self.canvas.create_polygon(
                sx - 180,
                GROUND_Y,
                sx,
                GROUND_Y - 120,
                sx + 210,
                GROUND_Y,
                fill="#22c55e",
                outline="",
            )

    def draw_platforms(self) -> None:
        for platform in self.platforms:
            sx, sy = self.world_to_screen(platform.x, platform.y)
            if sx > SCREEN_WIDTH or sx + platform.width < 0:
                continue

            self.canvas.create_rectangle(
                sx,
                sy,
                sx + platform.width,
                sy + platform.height,
                fill=platform.color,
                outline=BRICK_EDGE,
                width=2,
            )

            if platform.color == GROUND:
                self.canvas.create_rectangle(
                    sx,
                    sy + 18,
                    sx + platform.width,
                    sy + platform.height,
                    fill=DIRT,
                    outline="",
                )
            else:
                brick_x = sx
                while brick_x < sx + platform.width:
                    self.canvas.create_line(brick_x, sy, brick_x, sy + platform.height, fill=BRICK_EDGE)
                    brick_x += 32

    def draw_coins(self) -> None:
        for coin in self.coins:
            if coin.collected:
                continue
            sx, sy = self.world_to_screen(coin.x, coin.y)
            if -30 <= sx <= SCREEN_WIDTH + 30:
                self.canvas.create_oval(sx - 11, sy - 14, sx + 11, sy + 14, fill=COIN, outline="#ca8a04", width=2)
                self.canvas.create_line(sx, sy - 9, sx, sy + 9, fill="#fef08a", width=2)

    def draw_enemies(self) -> None:
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            sx, sy = self.world_to_screen(enemy.x, enemy.y)
            if sx > SCREEN_WIDTH or sx + enemy.width < 0:
                continue

            self.canvas.create_oval(sx, sy, sx + enemy.width, sy + enemy.height, fill=ENEMY, outline="#451a03", width=2)
            self.canvas.create_oval(sx + 8, sy + 8, sx + 13, sy + 13, fill="white", outline="")
            self.canvas.create_oval(sx + 22, sy + 8, sx + 27, sy + 13, fill="white", outline="")
            self.canvas.create_rectangle(sx + 4, sy + enemy.height - 4, sx + 14, sy + enemy.height + 4, fill="#451a03", outline="")
            self.canvas.create_rectangle(sx + 20, sy + enemy.height - 4, sx + 30, sy + enemy.height + 4, fill="#451a03", outline="")

    def draw_goal(self) -> None:
        pole_x = WORLD_WIDTH - 140
        sx, _ = self.world_to_screen(pole_x, 0)
        self.canvas.create_rectangle(sx, GROUND_Y - 190, sx + 8, GROUND_Y, fill="#f8fafc", outline="#94a3b8")
        self.canvas.create_polygon(
            sx + 8,
            GROUND_Y - 190,
            sx + 86,
            GROUND_Y - 160,
            sx + 8,
            GROUND_Y - 130,
            fill=FLAG,
            outline="#064e3b",
        )

    def draw_player(self) -> None:
        if self.player.invincible_ticks and (self.player.invincible_ticks // 6) % 2 == 0:
            return

        sx, sy = self.world_to_screen(self.player.x, self.player.y)
        self.canvas.create_rectangle(sx + 6, sy + 22, sx + 28, sy + 52, fill=PLAYER_BLUE, outline="#1e3a8a", width=2)
        self.canvas.create_oval(sx + 5, sy + 5, sx + 29, sy + 29, fill=PLAYER_SKIN, outline="#9a3412", width=2)
        self.canvas.create_rectangle(sx + 2, sy, sx + 32, sy + 12, fill=PLAYER_RED, outline="#7f1d1d", width=2)
        self.canvas.create_rectangle(sx + 10, sy + 12, sx + 24, sy + 24, fill=PLAYER_RED, outline="")
        self.canvas.create_oval(sx + 21, sy + 14, sx + 25, sy + 18, fill=TEXT, outline="")
        self.canvas.create_rectangle(sx + 3, sy + 50, sx + 14, sy + 58, fill="#451a03", outline="")
        self.canvas.create_rectangle(sx + 20, sy + 50, sx + 31, sy + 58, fill="#451a03", outline="")

    def draw_hud(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, 48, fill="#ffffff", outline="")
        hud = f"Score: {self.score}    Coins: {sum(coin.collected for coin in self.coins)}/{len(self.coins)}    Lives: {self.player.lives}"
        self.canvas.create_text(18, 24, text=hud, anchor="w", fill=TEXT, font=("Segoe UI", 14, "bold"))
        self.canvas.create_text(
            SCREEN_WIDTH - 18,
            24,
            text="Move: A/D or arrows   Jump: Space/Up/W   Restart: R",
            anchor="e",
            fill="#334155",
            font=("Segoe UI", 10),
        )

    def draw_center_banner(self, title: str, subtitle: str) -> None:
        self.canvas.create_rectangle(260, 190, 640, 330, fill="#f8fafc", outline=FLAG, width=3)
        self.canvas.create_text(450, 235, text=title, fill=TEXT, font=("Segoe UI", 28, "bold"))
        self.canvas.create_text(450, 280, text=subtitle, fill="#475569", font=("Segoe UI", 13))


def main() -> None:
    """Create the Tkinter root and hand control to Tkinter's event loop."""
    root = tk.Tk()
    try:
        root.iconname("Tkinter Pixel Runner")
    except tk.TclError:
        pass

    PixelRunnerTkinterGame(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except tk.TclError as exc:
        messagebox.showerror("Tkinter Pixel Runner", f"Could not start Tkinter: {exc}")
