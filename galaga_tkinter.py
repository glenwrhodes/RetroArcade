"""A Galaga-style fixed shooter built with Tkinter."""

from __future__ import annotations

import math
import random
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox


# Screen sizing, ship movement, projectile speeds, and colors are grouped for easy tuning.
SCREEN_WIDTH = 860
SCREEN_HEIGHT = 680
TICK_MS = 16

PLAYER_WIDTH = 48
PLAYER_HEIGHT = 34
PLAYER_Y = SCREEN_HEIGHT - 78
PLAYER_SPEED = 7.0

BULLET_WIDTH = 5
BULLET_HEIGHT = 18
PLAYER_BULLET_SPEED = -11.5
ENEMY_BULLET_SPEED = 5.0
MAX_PLAYER_BULLETS = 2

BACKGROUND = "#020617"
STAR = "#e2e8f0"
HUD_BG = "#0f172a"
TEXT = "#f8fafc"
MUTED = "#cbd5e1"
ACCENT = "#14b8a6"
PLAYER = "#22c55e"
PLAYER_SHADOW = "#15803d"
PLAYER_CANOPY = "#bae6fd"
BULLET = "#f8fafc"
ENEMY_BULLET = "#fb7185"
ENEMY_WINGS = ["#ef4444", "#f97316", "#facc15", "#38bdf8", "#a78bfa"]
ENEMY_BODY = "#111827"


# Entity dataclasses keep gameplay state separate from Tkinter canvas item details.
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


@dataclass
class Enemy:
    home_x: float
    home_y: float
    row: int
    col: int
    width: float = 42
    height: float = 30
    x: float = 0
    y: float = 0
    alive: bool = True
    diving: bool = False
    dive_style: str = "straight"
    dive_tick: int = 0
    dive_phase: float = 0
    dive_speed: float = 3.8
    loop_center_x: float = SCREEN_WIDTH / 2
    loop_start_y: float = 135
    loop_radius: float = 68
    loop_duration: int = 118

    def __post_init__(self) -> None:
        self.x = self.home_x
        self.y = self.home_y

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.width, self.height)

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    def formation_score(self) -> int:
        return 400 if self.row == 0 else 250 if self.row <= 2 else 150


class GalagaTkinterGame:
    """Manages formation enemies, diving attack patterns, bullets, collisions, and drawing."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tkinter Galaga")
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
        self.enemies: list[Enemy] = []
        self.player_bullets: list[Bullet] = []
        self.enemy_bullets: list[Bullet] = []
        self.stars: list[tuple[float, float, float]] = []
        self.score = 0
        self.wave = 1
        self.ticks = 0
        self.game_over = False
        self.wave_pause = 0
        self.after_id: str | None = None

        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.root.focus_set()

        self.restart()

    # Restart resets player/enemy state and seeds a new star field.
    def restart(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.keys.clear()
        self.player = PlayerShip()
        self.player_bullets = []
        self.enemy_bullets = []
        self.score = 0
        self.wave = 1
        self.ticks = 0
        self.game_over = False
        self.wave_pause = 0
        self.stars = [
            (random.randrange(SCREEN_WIDTH), random.randrange(SCREEN_HEIGHT), random.choice((0.7, 1.1, 1.7)))
            for _ in range(120)
        ]
        self.create_wave()
        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    # The wave builder creates the home formation that enemies return to after diving.
    def create_wave(self) -> None:
        self.enemies = []
        cols = 10
        rows = 5
        gap_x = 62
        gap_y = 48
        start_x = (SCREEN_WIDTH - (cols - 1) * gap_x) / 2 - 21
        start_y = 95

        for row in range(rows):
            for col in range(cols):
                # Stagger the top row to look like commander ships.
                if row == 0 and col in (0, 1, 8, 9):
                    continue
                self.enemies.append(
                    Enemy(
                        home_x=start_x + col * gap_x,
                        home_y=start_y + row * gap_y,
                        row=row,
                        col=col,
                        dive_phase=random.random() * math.tau,
                        dive_speed=3.5 + self.wave * 0.18 + row * 0.12,
                    )
                )

        self.player_bullets.clear()
        self.enemy_bullets.clear()

    # Input stores held keys; movement and firing are processed once per frame.
    def on_key_press(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        if key == "r":
            self.restart()
            return
        self.keys.add(key)

    def on_key_release(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym.lower())

    # Each tick scrolls the background, updates actors, resolves combat, and redraws.
    def update(self) -> None:
        self.after_id = None
        self.ticks += 1

        if not self.game_over:
            self.scroll_stars()
            if self.wave_pause > 0:
                self.wave_pause -= 1
                if self.wave_pause == 0:
                    self.wave += 1
                    self.create_wave()
            else:
                self.update_player()
                self.update_enemies()
                self.update_bullets()
                self.enemy_fire()
                self.handle_collisions()
                self.check_wave_state()

        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    def scroll_stars(self) -> None:
        updated = []
        for x, y, speed in self.stars:
            y += speed
            if y > SCREEN_HEIGHT:
                y = 0
                x = random.randrange(SCREEN_WIDTH)
            updated.append((x, y, speed))
        self.stars = updated

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

        self.player.x = max(18, min(self.player.x, SCREEN_WIDTH - self.player.width - 18))

        if firing and self.player.cooldown == 0 and len(self.player_bullets) < MAX_PLAYER_BULLETS:
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
            self.player.cooldown = 14

    def update_enemies(self) -> None:
        living = [enemy for enemy in self.enemies if enemy.alive]
        if not living:
            return

        sway = math.sin(self.ticks / 42) * (22 + min(self.wave, 8) * 2)
        bob = math.sin(self.ticks / 28) * 4

        for enemy in living:
            if enemy.diving:
                self.update_diving_enemy(enemy)
            else:
                enemy.x = enemy.home_x + sway
                enemy.y = enemy.home_y + bob + math.sin(self.ticks / 18 + enemy.col) * 2

        self.maybe_start_attack(living)

    # Diving attacks temporarily leave formation, then curve back after leaving the screen.
    def update_diving_enemy(self, enemy: Enemy) -> None:
        enemy.dive_tick += 1

        if enemy.dive_style == "loop" and enemy.dive_tick <= enemy.loop_duration:
            angle = enemy.dive_tick / 13 + enemy.dive_phase
            center_x = enemy.loop_center_x + math.sin(enemy.dive_tick / 38) * 35
            center_y = enemy.loop_start_y + enemy.dive_tick * (1.45 + self.wave * 0.03)
            enemy.x = center_x + math.cos(angle) * enemy.loop_radius - enemy.width / 2
            enemy.y = center_y + math.sin(angle) * enemy.loop_radius - enemy.height / 2
            return

        target_pull = (self.player.x + self.player.width / 2 - enemy.center_x) * 0.018
        wave_x = math.sin(enemy.dive_tick / 8 + enemy.dive_phase) * (5 + self.wave * 0.3)
        enemy.x += target_pull + wave_x
        enemy.y += enemy.dive_speed + math.sin(enemy.dive_tick / 11) * 1.8

        if enemy.y > SCREEN_HEIGHT + 50:
            self.return_enemy_to_formation(enemy)

    # Attack selection alternates between single dives and grouped looping patterns.
    def maybe_start_attack(self, living: list[Enemy]) -> None:
        active_dives = sum(1 for enemy in living if enemy.diving)
        max_dives = 1 + min(self.wave // 2, 3)
        if active_dives >= max_dives:
            return

        chance = min(0.014 + self.wave * 0.0025, 0.04)
        if random.random() > chance:
            return

        can_launch_group = active_dives == 0 and len([enemy for enemy in living if not enemy.diving]) >= 3
        if can_launch_group and random.random() < 0.42:
            self.start_loop_attack(living)
        else:
            self.start_single_dive(living)

    def start_single_dive(self, living: list[Enemy]) -> None:
        candidates = [enemy for enemy in living if not enemy.diving]
        if not candidates:
            return

        attacker = random.choice(candidates)
        attacker.diving = True
        attacker.dive_style = "straight"
        attacker.dive_tick = 0
        attacker.dive_phase = random.random() * math.tau

    def start_loop_attack(self, living: list[Enemy]) -> None:
        candidates = [enemy for enemy in living if not enemy.diving]
        row_groups: dict[int, list[Enemy]] = {}
        for enemy in candidates:
            row_groups.setdefault(enemy.row, []).append(enemy)

        possible_rows = [row for row, enemies in row_groups.items() if len(enemies) >= 3]
        if not possible_rows:
            self.start_single_dive(living)
            return

        row = random.choice(possible_rows)
        row_enemies = sorted(row_groups[row], key=lambda enemy: enemy.col)
        group_size = min(len(row_enemies), random.choice((3, 4, 5)))
        start_index = random.randrange(0, len(row_enemies) - group_size + 1)
        attackers = row_enemies[start_index : start_index + group_size]

        center_x = sum(enemy.home_x + enemy.width / 2 for enemy in attackers) / len(attackers)
        center_x = max(150, min(center_x, SCREEN_WIDTH - 150))
        loop_start_y = min(enemy.home_y for enemy in attackers) + 55

        for index, enemy in enumerate(attackers):
            enemy.diving = True
            enemy.dive_style = "loop"
            enemy.dive_tick = 0
            enemy.dive_phase = math.tau * index / len(attackers)
            enemy.loop_center_x = center_x
            enemy.loop_start_y = loop_start_y
            enemy.loop_radius = 58 + len(attackers) * 7
            enemy.loop_duration = 104 + len(attackers) * 8

    def return_enemy_to_formation(self, enemy: Enemy) -> None:
        enemy.diving = False
        enemy.dive_style = "straight"
        enemy.dive_tick = 0
        enemy.x = enemy.home_x
        enemy.y = enemy.home_y

    def update_bullets(self) -> None:
        for bullet in self.player_bullets + self.enemy_bullets:
            bullet.update()

        self.player_bullets = [bullet for bullet in self.player_bullets if bullet.bottom > 0]
        self.enemy_bullets = [bullet for bullet in self.enemy_bullets if bullet.top < SCREEN_HEIGHT]

    # Diving enemies are preferred shooters so active attacks feel more dangerous.
    def enemy_fire(self) -> None:
        living = [enemy for enemy in self.enemies if enemy.alive]
        if not living:
            return

        chance = min(0.016 + self.wave * 0.003, 0.05)
        if random.random() > chance:
            return

        divers = [enemy for enemy in living if enemy.diving]
        shooter = random.choice(divers or living)
        self.enemy_bullets.append(
            Bullet(
                x=shooter.center_x - BULLET_WIDTH / 2,
                y=shooter.center_y,
                width=BULLET_WIDTH,
                height=BULLET_HEIGHT,
                speed=ENEMY_BULLET_SPEED + self.wave * 0.18,
                from_player=False,
            )
        )

    # Collision methods separate player damage from scoring enemy hits.
    def handle_collisions(self) -> None:
        self.handle_player_hits()
        self.handle_enemy_hits()

    def handle_player_hits(self) -> None:
        if self.player.invincible_ticks > 0:
            return

        hit_by_bullet = any(bullet.intersects(self.player.rect) for bullet in self.enemy_bullets)
        hit_by_enemy = any(enemy.alive and enemy.rect.intersects(self.player.rect) for enemy in self.enemies)

        if hit_by_bullet or hit_by_enemy:
            self.damage_player()

    def handle_enemy_hits(self) -> None:
        remaining_bullets: list[Bullet] = []

        for bullet in self.player_bullets:
            hit_enemy = None
            for enemy in self.enemies:
                if enemy.alive and bullet.intersects(enemy.rect):
                    hit_enemy = enemy
                    break

            if hit_enemy is None:
                remaining_bullets.append(bullet)
                continue

            hit_enemy.alive = False
            dive_bonus = 2 if hit_enemy.diving else 1
            self.score += hit_enemy.formation_score() * dive_bonus

        self.player_bullets = remaining_bullets

    def damage_player(self) -> None:
        self.player.lives -= 1
        self.enemy_bullets.clear()
        self.player.invincible_ticks = 115
        self.player.x = SCREEN_WIDTH / 2 - PLAYER_WIDTH / 2

        for enemy in self.enemies:
            if enemy.diving:
                self.return_enemy_to_formation(enemy)

        if self.player.lives <= 0:
            self.game_over = True

    def check_wave_state(self) -> None:
        if all(not enemy.alive for enemy in self.enemies):
            self.score += self.wave * 1000
            self.wave_pause = 110

    # Rendering is rebuilt from state so canvas objects never need to be tracked individually.
    def draw(self) -> None:
        self.canvas.delete("all")
        self.draw_background()
        self.draw_hud()
        self.draw_bullets()
        self.draw_enemies()
        self.draw_player()

        if self.wave_pause > 0 and not self.game_over:
            self.draw_center_banner("Wave Cleared", f"Prepare for wave {self.wave + 1}")
        elif self.game_over:
            self.draw_center_banner("Game Over", "Press R to restart")

    def draw_background(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, fill=BACKGROUND, outline="")
        for x, y, speed in self.stars:
            radius = 1 if speed < 1 else 2
            color = "#64748b" if speed < 1 else STAR
            self.canvas.create_oval(x, y, x + radius, y + radius, fill=color, outline="")

    def draw_hud(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, 54, fill=HUD_BG, outline="#1e293b")
        self.canvas.create_text(
            20,
            27,
            text=f"Score: {self.score}    Lives: {self.player.lives}    Wave: {self.wave}",
            anchor="w",
            fill=TEXT,
            font=("Segoe UI", 14, "bold"),
        )
        self.canvas.create_text(
            SCREEN_WIDTH - 20,
            27,
            text="Move: A/D or arrows   Fire: Space/Up/W   Restart: R",
            anchor="e",
            fill=MUTED,
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
            outline=PLAYER_SHADOW,
            width=2,
        )
        self.canvas.create_polygon(
            x + 8,
            y + PLAYER_HEIGHT,
            x + PLAYER_WIDTH / 2,
            y + 12,
            x + PLAYER_WIDTH - 8,
            y + PLAYER_HEIGHT,
            fill=PLAYER_SHADOW,
            outline="",
        )
        self.canvas.create_oval(x + 18, y + 9, x + 30, y + 22, fill=PLAYER_CANOPY, outline="#0369a1")
        self.canvas.create_rectangle(x + 6, y + 28, x + 16, y + 39, fill="#f97316", outline="")
        self.canvas.create_rectangle(x + 32, y + 28, x + 42, y + 39, fill="#f97316", outline="")

    def draw_enemies(self) -> None:
        for enemy in self.enemies:
            if not enemy.alive:
                continue

            x = enemy.x
            y = enemy.y
            wing = ENEMY_WINGS[enemy.row % len(ENEMY_WINGS)]
            body = "#f8fafc" if enemy.row == 0 else ENEMY_BODY

            if enemy.diving and enemy.dive_style == "loop":
                self.canvas.create_oval(
                    x - 16,
                    y - 16,
                    x + enemy.width + 16,
                    y + enemy.height + 16,
                    outline=ACCENT,
                    width=2,
                )
            elif enemy.diving:
                self.canvas.create_arc(x - 8, y - 8, x + enemy.width + 8, y + enemy.height + 18, start=210, extent=120, outline=ACCENT, width=2)

            self.canvas.create_polygon(
                x,
                y + 8,
                x + 12,
                y + enemy.height,
                x + enemy.width / 2,
                y + 18,
                x + enemy.width - 12,
                y + enemy.height,
                x + enemy.width,
                y + 8,
                fill=wing,
                outline="#0f172a",
                width=2,
            )
            self.canvas.create_oval(
                x + 10,
                y,
                x + enemy.width - 10,
                y + enemy.height,
                fill=body,
                outline=wing,
                width=2,
            )
            self.canvas.create_oval(x + 16, y + 9, x + 21, y + 14, fill=wing, outline="")
            self.canvas.create_oval(x + enemy.width - 21, y + 9, x + enemy.width - 16, y + 14, fill=wing, outline="")

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

        for bullet in self.enemy_bullets:
            self.canvas.create_oval(
                bullet.x - 2,
                bullet.y,
                bullet.x + bullet.width + 2,
                bullet.y + bullet.height,
                fill=ENEMY_BULLET,
                outline="",
            )

    def draw_center_banner(self, title: str, subtitle: str) -> None:
        self.canvas.create_rectangle(242, 255, 618, 390, fill=HUD_BG, outline=ACCENT, width=3)
        self.canvas.create_text(430, 300, text=title, fill=TEXT, font=("Segoe UI", 28, "bold"))
        self.canvas.create_text(430, 343, text=subtitle, fill=MUTED, font=("Segoe UI", 13))


def main() -> None:
    """Create the Tkinter root and hand control to Tkinter's event loop."""
    root = tk.Tk()
    try:
        root.iconname("Tkinter Galaga")
    except tk.TclError:
        pass

    GalagaTkinterGame(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except tk.TclError as exc:
        messagebox.showerror("Tkinter Galaga", f"Could not start Tkinter: {exc}")
