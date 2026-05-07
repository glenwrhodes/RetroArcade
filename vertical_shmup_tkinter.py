"""A vertical scrolling shoot-'em-up with a boss fight, built with Tkinter."""

from __future__ import annotations

import math
import random
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox


SCREEN_WIDTH = 760
SCREEN_HEIGHT = 720
TICK_MS = 16

PLAYER_WIDTH = 42
PLAYER_HEIGHT = 50
PLAYER_SPEED = 6.3
PLAYER_Y = SCREEN_HEIGHT - 105

BULLET_WIDTH = 5
BULLET_HEIGHT = 18
PLAYER_BULLET_SPEED = -12.5
ENEMY_BULLET_SPEED = 4.6

BACKGROUND = "#07111f"
WATER = "#0b3553"
LAND = "#25451f"
PLAYER = "#38bdf8"
PLAYER_DARK = "#075985"
PLAYER_FIRE = "#f97316"
ENEMY = "#ef4444"
ENEMY_ALT = "#f59e0b"
GROUND_TARGET = "#a16207"
BOSS = "#7c3aed"
BOSS_DARK = "#3b0764"
BULLET = "#f8fafc"
ENEMY_BULLET = "#fb7185"
POWERUP = "#22c55e"
TEXT = "#f8fafc"
MUTED = "#cbd5e1"
HUD = "#0f172a"
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
class Bullet(Rect):
    vx: float
    vy: float
    from_player: bool

    def update(self) -> None:
        self.x += self.vx
        self.y += self.vy


@dataclass
class Enemy(Rect):
    kind: str
    vx: float
    vy: float
    health: int
    fire_timer: int
    phase: float

    def update(self, tick: int) -> None:
        if self.kind == "zigzag":
            self.x += math.sin(tick / 18 + self.phase) * 2.2
        elif self.kind == "swooper":
            self.x += self.vx + math.sin(tick / 10 + self.phase) * 3.0
        else:
            self.x += self.vx
        self.y += self.vy


@dataclass
class PowerUp(Rect):
    kind: str = "spread"
    vy: float = 2.4

    def update(self) -> None:
        self.y += self.vy


@dataclass
class Player:
    x: float = SCREEN_WIDTH / 2 - PLAYER_WIDTH / 2
    y: float = PLAYER_Y
    width: float = PLAYER_WIDTH
    height: float = PLAYER_HEIGHT
    lives: int = 3
    cooldown: int = 0
    invincible_ticks: int = 0
    weapon_level: int = 1

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.width, self.height)


@dataclass
class Boss:
    x: float = SCREEN_WIDTH / 2 - 90
    y: float = -150
    width: float = 180
    height: float = 110
    health: int = 160
    max_health: int = 160
    vx: float = 2.4
    phase_ticks: int = 0
    alive: bool = True

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.width, self.height)


class VerticalShmupGame:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tkinter Vertical Shmup")
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
        self.player_bullets: list[Bullet] = []
        self.enemy_bullets: list[Bullet] = []
        self.enemies: list[Enemy] = []
        self.powerups: list[PowerUp] = []
        self.boss: Boss | None = None
        self.terrain: list[tuple[float, float, float, str]] = []
        self.tick_count = 0
        self.distance = 0
        self.score = 0
        self.game_over = False
        self.victory = False
        self.boss_warning = 0
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
        self.player = Player()
        self.player_bullets = []
        self.enemy_bullets = []
        self.enemies = []
        self.powerups = []
        self.boss = None
        self.tick_count = 0
        self.distance = 0
        self.score = 0
        self.game_over = False
        self.victory = False
        self.boss_warning = 0
        self.terrain = self.create_terrain()
        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    def create_terrain(self) -> list[tuple[float, float, float, str]]:
        terrain = []
        for _ in range(38):
            terrain.append(
                (
                    random.randrange(0, SCREEN_WIDTH),
                    random.randrange(0, SCREEN_HEIGHT),
                    random.choice((1.2, 1.7, 2.3, 2.9)),
                    random.choice(("wake", "wake", "wake", "island", "reef")),
                )
            )
        return terrain

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

        if not self.game_over and not self.victory:
            self.distance += 1
            self.scroll_terrain()
            self.update_player()
            self.spawn_enemies()
            self.update_enemies()
            self.update_boss()
            self.update_bullets()
            self.update_powerups()
            self.handle_collisions()
            self.cleanup_objects()

        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    def scroll_terrain(self) -> None:
        updated = []
        speed_bonus = 0.6 if self.boss is None else 0.15
        for x, y, speed, kind in self.terrain:
            y += speed + speed_bonus
            if y > SCREEN_HEIGHT + 40:
                y = random.randrange(-120, -20)
                x = random.randrange(0, SCREEN_WIDTH)
                kind = random.choice(("wake", "wake", "wake", "island", "reef"))
            updated.append((x, y, speed, kind))
        self.terrain = updated

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
            dy -= PLAYER_SPEED * 0.82
        if "down" in self.keys or "s" in self.keys:
            dy += PLAYER_SPEED * 0.82

        if dx and dy:
            dx *= 0.72
            dy *= 0.72

        self.player.x = max(18, min(self.player.x + dx, SCREEN_WIDTH - self.player.width - 18))
        self.player.y = max(82, min(self.player.y + dy, SCREEN_HEIGHT - self.player.height - 28))

        firing = "space" in self.keys or "up" in self.keys or "w" in self.keys
        if firing and self.player.cooldown == 0:
            self.fire_player_bullets()
            self.player.cooldown = max(7, 13 - self.player.weapon_level)

    def fire_player_bullets(self) -> None:
        center = self.player.x + self.player.width / 2 - BULLET_WIDTH / 2
        y = self.player.y - BULLET_HEIGHT
        self.player_bullets.append(Bullet(center, y, BULLET_WIDTH, BULLET_HEIGHT, 0, PLAYER_BULLET_SPEED, True))

        if self.player.weapon_level >= 2:
            self.player_bullets.append(Bullet(center - 14, y + 5, BULLET_WIDTH, BULLET_HEIGHT, -1.6, PLAYER_BULLET_SPEED + 0.6, True))
            self.player_bullets.append(Bullet(center + 14, y + 5, BULLET_WIDTH, BULLET_HEIGHT, 1.6, PLAYER_BULLET_SPEED + 0.6, True))

        if self.player.weapon_level >= 3:
            self.player_bullets.append(Bullet(center - 24, y + 10, BULLET_WIDTH, BULLET_HEIGHT, -2.8, PLAYER_BULLET_SPEED + 1.2, True))
            self.player_bullets.append(Bullet(center + 24, y + 10, BULLET_WIDTH, BULLET_HEIGHT, 2.8, PLAYER_BULLET_SPEED + 1.2, True))

    def spawn_enemies(self) -> None:
        if self.boss is not None:
            return

        if self.distance == 1850:
            self.boss_warning = 150
        if self.distance >= 2050:
            self.boss = Boss()
            self.enemies.clear()
            self.enemy_bullets.clear()
            return

        if self.tick_count % 58 == 0:
            self.spawn_basic_pair()
        if self.tick_count % 145 == 0:
            self.spawn_zigzag_wave()
        if self.tick_count % 230 == 0:
            self.spawn_ground_targets()

    def spawn_basic_pair(self) -> None:
        x = random.randrange(60, SCREEN_WIDTH - 120)
        for offset in (0, 68):
            self.enemies.append(
                Enemy(
                    x=x + offset,
                    y=-45,
                    width=38,
                    height=32,
                    kind="fighter",
                    vx=random.choice((-0.8, 0.8)),
                    vy=random.uniform(2.2, 3.1),
                    health=1,
                    fire_timer=random.randrange(60, 130),
                    phase=random.random() * math.tau,
                )
            )

    def spawn_zigzag_wave(self) -> None:
        from_left = random.choice((True, False))
        start_x = -40 if from_left else SCREEN_WIDTH + 40
        vx = 2.4 if from_left else -2.4
        for index in range(5):
            self.enemies.append(
                Enemy(
                    x=start_x - index * vx * 12,
                    y=-40 - index * 34,
                    width=36,
                    height=30,
                    kind="swooper",
                    vx=vx,
                    vy=2.9,
                    health=1,
                    fire_timer=random.randrange(85, 155),
                    phase=index * 0.8,
                )
            )

    def spawn_ground_targets(self) -> None:
        for _ in range(3):
            self.enemies.append(
                Enemy(
                    x=random.randrange(70, SCREEN_WIDTH - 110),
                    y=random.randrange(-180, -50),
                    width=46,
                    height=34,
                    kind="ground",
                    vx=0,
                    vy=2.05,
                    health=2,
                    fire_timer=random.randrange(95, 180),
                    phase=random.random() * math.tau,
                )
            )

    def update_enemies(self) -> None:
        for enemy in self.enemies:
            enemy.update(self.tick_count)
            enemy.fire_timer -= 1
            if enemy.fire_timer <= 0 and enemy.bottom > 0:
                self.fire_enemy_bullet(enemy)
                enemy.fire_timer = random.randrange(85, 165)

    def update_boss(self) -> None:
        if self.boss is None or not self.boss.alive:
            return

        boss = self.boss
        boss.phase_ticks += 1
        if boss.y < 78:
            boss.y += 1.7
        else:
            boss.x += boss.vx
            if boss.x < 48 or boss.x + boss.width > SCREEN_WIDTH - 48:
                boss.vx *= -1

        if boss.phase_ticks % 42 == 0:
            self.fire_boss_spread()
        if boss.phase_ticks % 130 == 0:
            self.spawn_boss_minions()

    def fire_enemy_bullet(self, source: Rect) -> None:
        target_x = self.player.x + self.player.width / 2
        dx = max(-2.0, min((target_x - source.center_x) / 90, 2.0))
        self.enemy_bullets.append(
            Bullet(
                x=source.center_x - BULLET_WIDTH / 2,
                y=source.bottom,
                width=BULLET_WIDTH,
                height=BULLET_HEIGHT,
                vx=dx,
                vy=ENEMY_BULLET_SPEED,
                from_player=False,
            )
        )

    def fire_boss_spread(self) -> None:
        if self.boss is None:
            return

        for angle in (-0.55, -0.28, 0, 0.28, 0.55):
            self.enemy_bullets.append(
                Bullet(
                    x=self.boss.x + self.boss.width / 2 - BULLET_WIDTH / 2,
                    y=self.boss.y + self.boss.height - 8,
                    width=BULLET_WIDTH,
                    height=BULLET_HEIGHT,
                    vx=math.sin(angle) * 4.0,
                    vy=ENEMY_BULLET_SPEED + math.cos(angle),
                    from_player=False,
                )
            )

    def spawn_boss_minions(self) -> None:
        if self.boss is None:
            return

        for side in (-1, 1):
            self.enemies.append(
                Enemy(
                    x=self.boss.x + self.boss.width / 2 + side * 74,
                    y=self.boss.y + self.boss.height - 8,
                    width=34,
                    height=28,
                    kind="zigzag",
                    vx=side * 1.1,
                    vy=3.1,
                    health=1,
                    fire_timer=random.randrange(75, 125),
                    phase=random.random() * math.tau,
                )
            )

    def update_bullets(self) -> None:
        for bullet in self.player_bullets + self.enemy_bullets:
            bullet.update()

    def update_powerups(self) -> None:
        for powerup in self.powerups:
            powerup.update()

    def handle_collisions(self) -> None:
        self.handle_player_bullet_hits()
        self.handle_player_damage()
        self.handle_powerups()

    def handle_player_bullet_hits(self) -> None:
        remaining_bullets: list[Bullet] = []
        for bullet in self.player_bullets:
            hit = False

            for enemy in self.enemies:
                if enemy.health > 0 and bullet.intersects(enemy):
                    enemy.health -= 1
                    hit = True
                    if enemy.health <= 0:
                        self.score += 175 if enemy.kind != "ground" else 250
                        if random.random() < 0.09:
                            self.powerups.append(PowerUp(enemy.center_x - 13, enemy.center_y - 13, 26, 26))
                    break

            if not hit and self.boss is not None and self.boss.alive and bullet.intersects(self.boss.rect):
                self.boss.health -= 1
                self.score += 15
                hit = True
                if self.boss.health <= 0:
                    self.boss.alive = False
                    self.score += 5000
                    self.victory = True

            if not hit:
                remaining_bullets.append(bullet)

        self.player_bullets = remaining_bullets

    def handle_player_damage(self) -> None:
        if self.player.invincible_ticks > 0:
            return

        player_rect = self.player.rect
        bullet_hit = any(bullet.intersects(player_rect) for bullet in self.enemy_bullets)
        enemy_hit = any(enemy.health > 0 and enemy.intersects(player_rect) for enemy in self.enemies)
        boss_hit = self.boss is not None and self.boss.alive and self.boss.rect.intersects(player_rect)

        if bullet_hit or enemy_hit or boss_hit:
            self.damage_player()

    def handle_powerups(self) -> None:
        remaining: list[PowerUp] = []
        for powerup in self.powerups:
            if powerup.intersects(self.player.rect):
                self.player.weapon_level = min(3, self.player.weapon_level + 1)
                self.score += 500
            else:
                remaining.append(powerup)
        self.powerups = remaining

    def damage_player(self) -> None:
        self.player.lives -= 1
        self.player.invincible_ticks = 125
        self.player.weapon_level = max(1, self.player.weapon_level - 1)
        self.enemy_bullets.clear()
        self.player.x = SCREEN_WIDTH / 2 - self.player.width / 2
        self.player.y = PLAYER_Y

        if self.player.lives <= 0:
            self.game_over = True

    def cleanup_objects(self) -> None:
        self.enemies = [
            enemy
            for enemy in self.enemies
            if enemy.health > 0 and enemy.y < SCREEN_HEIGHT + 80 and -90 < enemy.x < SCREEN_WIDTH + 90
        ]
        self.player_bullets = [bullet for bullet in self.player_bullets if bullet.bottom > -30]
        self.enemy_bullets = [bullet for bullet in self.enemy_bullets if bullet.top < SCREEN_HEIGHT + 40]
        self.powerups = [powerup for powerup in self.powerups if powerup.top < SCREEN_HEIGHT + 30]

    def draw(self) -> None:
        self.canvas.delete("all")
        self.draw_background()
        self.draw_hud()
        self.draw_powerups()
        self.draw_enemies()
        self.draw_boss()
        self.draw_bullets()
        self.draw_player()

        if self.boss_warning > 0 and self.boss is None:
            self.boss_warning -= 1
            self.draw_center_banner("WARNING", "Boss aircraft approaching")
        if self.victory:
            self.draw_center_banner("Mission Complete", "Press R to fly again")
        elif self.game_over:
            self.draw_center_banner("Game Over", "Press R to restart")

    def draw_background(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, fill=WATER, outline="")
        self.canvas.create_polygon(0, 0, 120, 0, 70, SCREEN_HEIGHT, 0, SCREEN_HEIGHT, fill=LAND, outline="")
        self.canvas.create_polygon(
            SCREEN_WIDTH,
            0,
            SCREEN_WIDTH - 95,
            0,
            SCREEN_WIDTH - 55,
            SCREEN_HEIGHT,
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
            fill=LAND,
            outline="",
        )

        for x, y, speed, kind in self.terrain:
            if kind == "wake":
                self.canvas.create_line(x - 16, y, x + 16, y + 6, fill="#7dd3fc", width=2)
            elif kind == "reef":
                self.canvas.create_oval(x - 12, y - 5, x + 12, y + 5, fill="#164e63", outline="")
            else:
                self.canvas.create_polygon(
                    x - 18,
                    y,
                    x - 7,
                    y - 10,
                    x + 15,
                    y - 7,
                    x + 20,
                    y + 7,
                    x + 4,
                    y + 13,
                    x - 15,
                    y + 8,
                    fill="#3f6212",
                    outline="",
                )

    def draw_hud(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, 56, fill=HUD, outline="#1e293b")
        self.canvas.create_text(
            18,
            28,
            text=f"Score: {self.score}    Lives: {self.player.lives}    Weapon: {self.player.weapon_level}",
            anchor="w",
            fill=TEXT,
            font=("Segoe UI", 14, "bold"),
        )
        status = "Boss Fight" if self.boss is not None else f"Distance: {min(self.distance, 2050)}/2050"
        self.canvas.create_text(SCREEN_WIDTH - 18, 28, text=status, anchor="e", fill=MUTED, font=("Segoe UI", 11))

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
            y + PLAYER_HEIGHT - 12,
            x,
            y + PLAYER_HEIGHT,
            fill=PLAYER,
            outline=PLAYER_DARK,
            width=2,
        )
        self.canvas.create_oval(x + 14, y + 15, x + 28, y + 31, fill="#e0f2fe", outline=PLAYER_DARK)
        self.canvas.create_polygon(x + 10, y + PLAYER_HEIGHT, x + 18, y + PLAYER_HEIGHT + 14, x + 24, y + PLAYER_HEIGHT, fill=PLAYER_FIRE, outline="")
        self.canvas.create_polygon(x + 24, y + PLAYER_HEIGHT, x + 31, y + PLAYER_HEIGHT + 14, x + 36, y + PLAYER_HEIGHT, fill=PLAYER_FIRE, outline="")

    def draw_enemies(self) -> None:
        for enemy in self.enemies:
            if enemy.health <= 0:
                continue
            if enemy.kind == "ground":
                self.canvas.create_rectangle(enemy.x, enemy.y, enemy.x + enemy.width, enemy.y + enemy.height, fill=GROUND_TARGET, outline="#422006", width=2)
                self.canvas.create_oval(enemy.x + 13, enemy.y + 7, enemy.x + 33, enemy.y + 27, fill="#451a03", outline="")
            else:
                color = ENEMY_ALT if enemy.kind == "swooper" else ENEMY
                self.canvas.create_polygon(
                    enemy.x + enemy.width / 2,
                    enemy.y + enemy.height,
                    enemy.x,
                    enemy.y,
                    enemy.x + enemy.width / 2,
                    enemy.y + 10,
                    enemy.x + enemy.width,
                    enemy.y,
                    fill=color,
                    outline="#7f1d1d",
                    width=2,
                )
                self.canvas.create_oval(enemy.x + 12, enemy.y + 10, enemy.x + enemy.width - 12, enemy.y + enemy.height - 2, fill="#111827", outline=color)

    def draw_boss(self) -> None:
        if self.boss is None or not self.boss.alive:
            return

        boss = self.boss
        self.canvas.create_polygon(
            boss.x,
            boss.y + 34,
            boss.x + boss.width / 2,
            boss.y,
            boss.x + boss.width,
            boss.y + 34,
            boss.x + boss.width - 38,
            boss.y + boss.height,
            boss.x + boss.width / 2,
            boss.y + 78,
            boss.x + 38,
            boss.y + boss.height,
            fill=BOSS,
            outline=BOSS_DARK,
            width=3,
        )
        self.canvas.create_oval(boss.x + 64, boss.y + 28, boss.x + 116, boss.y + 70, fill="#c4b5fd", outline=BOSS_DARK)
        self.canvas.create_rectangle(150, 64, SCREEN_WIDTH - 150, 78, fill="#1e293b", outline="")
        health_width = (SCREEN_WIDTH - 300) * max(0, boss.health) / boss.max_health
        self.canvas.create_rectangle(150, 64, 150 + health_width, 78, fill="#ef4444", outline="")
        self.canvas.create_text(SCREEN_WIDTH / 2, 51, text="BOSS", fill=TEXT, font=("Segoe UI", 10, "bold"))

    def draw_bullets(self) -> None:
        for bullet in self.player_bullets:
            self.canvas.create_rectangle(bullet.x, bullet.y, bullet.x + bullet.width, bullet.y + bullet.height, fill=BULLET, outline="")
        for bullet in self.enemy_bullets:
            self.canvas.create_oval(bullet.x - 3, bullet.y, bullet.x + bullet.width + 3, bullet.y + bullet.height, fill=ENEMY_BULLET, outline="")

    def draw_powerups(self) -> None:
        for powerup in self.powerups:
            self.canvas.create_oval(powerup.x, powerup.y, powerup.x + powerup.width, powerup.y + powerup.height, fill=POWERUP, outline="#14532d", width=2)
            self.canvas.create_text(powerup.center_x, powerup.center_y, text="+", fill=TEXT, font=("Segoe UI", 12, "bold"))

    def draw_center_banner(self, title: str, subtitle: str) -> None:
        self.canvas.create_rectangle(190, 292, 570, 422, fill=HUD, outline=ACCENT, width=3)
        self.canvas.create_text(SCREEN_WIDTH / 2, 334, text=title, fill=TEXT, font=("Segoe UI", 27, "bold"))
        self.canvas.create_text(SCREEN_WIDTH / 2, 376, text=subtitle, fill=MUTED, font=("Segoe UI", 13))


def main() -> None:
    root = tk.Tk()
    try:
        root.iconname("Tkinter Vertical Shmup")
    except tk.TclError:
        pass

    VerticalShmupGame(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except tk.TclError as exc:
        messagebox.showerror("Tkinter Vertical Shmup", f"Could not start Tkinter: {exc}")
