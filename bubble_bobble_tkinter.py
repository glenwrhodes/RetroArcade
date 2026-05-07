"""A Bubble Bobble-style platform game built with Tkinter."""

from __future__ import annotations

import hashlib
import random
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None


# Screen size, physics tuning, entity sizes, tile layout, and palette constants.
SCREEN_WIDTH = 820
SCREEN_HEIGHT = 640
TICK_MS = 16

GRAVITY = 0.55
PLAYER_SPEED = 4.8
JUMP_SPEED = -12.5
MAX_PLAYER_FALL_SPEED = 4.4
ENEMY_SPEED = 1.7

PLAYER_WIDTH = 30
PLAYER_HEIGHT = 30
PLAYER_COLLISION_WIDTH_SCALE = 0.8
BUBBLE_SIZE = 34

BACKGROUND = "#0f172a"
WALL = "#1e293b"
PLATFORM = "#14b8a6"
PLATFORM_DARK = "#0f766e"
PLAYER = "#22c55e"
PLAYER_DARK = "#15803d"
PLAYER_BELLY = "#dcfce7"
ENEMY = "#f97316"
ENEMY_DARK = "#9a3412"
AIR_ENEMY = "#38bdf8"
AIR_ENEMY_DARK = "#075985"
BUBBLE = "#bae6fd"
BUBBLE_EDGE = "#38bdf8"
FRUIT = "#fb7185"
TEXT = "#f8fafc"
MUTED = "#cbd5e1"
PANEL = "#020617"
ACCENT = "#facc15"

TILE_SIZE = 32
MAP_X = 10
MAP_Y = 56

# Hand-authored fallback maps keep the game playable when Pillow or suitable fonts are missing.
FALLBACK_LEVEL_MAPS = [
    {
        "name": "Kana Gate",
        "rows": [
            "#########################",
            "#..........A............#",
            "#.......................#",
            "#..####...........####..#",
            "#.......................#",
            "#.......W.......W.......#",
            "#.....######...######...#",
            "#.......................#",
            "#...........####........#",
            "#.......................#",
            "#..####...........####..#",
            "#.......................#",
            "#....W...............W..#",
            "#.....######...######...#",
            "#.......................#",
            "#..P....................#",
            "#.......................#",
            "#########################",
        ],
    },
    {
        "name": "River Glyph",
        "rows": [
            "#########################",
            "#....A.............A....#",
            "#.......................#",
            "#..........#####........#",
            "#.........#.....#.......#",
            "#....W...#.......#...W..#",
            "#.......#.........#.....#",
            "#......#####...#####....#",
            "#.......................#",
            "#..####.............#####",
            "#.......................#",
            "#.....#####...#####.....#",
            "#....W.............W....#",
            "#.......................#",
            "#..........#####........#",
            "#..P....................#",
            "#.......................#",
            "#########################",
        ],
    },
    {
        "name": "Mountain Mark",
        "rows": [
            "#########################",
            "#...A.........A.....A...#",
            "#.......................#",
            "#...........###.........#",
            "#..........#####........#",
            "#.....W...#######...W...#",
            "#.......................#",
            "#......####...####......#",
            "#.......................#",
            "#..###.............###..#",
            "#.......................#",
            "#.....#####...#####.....#",
            "#..W...............W....#",
            "#.......................#",
            "#.........#######.......#",
            "#..P....................#",
            "#.......................#",
            "#########################",
        ],
    },
    {
        "name": "Box Maze",
        "rows": [
            "#########################",
            "#..A.....A......A.....A.#",
            "#.......................#",
            "#..#####.........#####..#",
            "#..#.................#..#",
            "#..#...W.........W...#..#",
            "#..#####.........#####..#",
            "#.......................#",
            "#.......####.####.......#",
            "#.......................#",
            "#..#####.........#####..#",
            "#..#.................#..#",
            "#..#...W.........W...#..#",
            "#..#####.........#####..#",
            "#.......................#",
            "#..P....................#",
            "#.......................#",
            "#########################",
        ],
    },
]

# Optional glyph recipes generate many more maze layouts from rendered character masks.
GLYPH_LEVEL_SPECS = [
    ("Mountain Cut", "山", "三", "subtract"),
    ("River Lattice", "川", "王", "xor"),
    ("Field Windows", "田", "十", "xor"),
    ("Gate Cutouts", "門", "日", "subtract"),
    ("Tree Rooms", "木", "田", "xor"),
    ("Moon Cut", "月", "二", "subtract"),
    ("Tower Mask", "中", "工", "mask"),
    ("Forest Lattice", "林", "王", "xor"),
    ("Gate Terraces", "門", "三", "subtract"),
    ("Temple Windows", "宮", "田", "xor"),
    ("Stone Steps", "石", "三", "or"),
    ("Firebreak", "火", "十", "xor"),
    ("Water Channels", "水", "二", "subtract"),
    ("Gold Rooms", "金", "日", "xor"),
    ("East Cut", "東", "口", "subtract"),
    ("West Maze", "西", "十", "xor"),
    ("South Gate", "南", "工", "subtract"),
    ("North Lattice", "北", "王", "or"),
    ("Sky Bridge", "空", "二", "subtract"),
    ("Rain Holes", "雨", "日", "xor"),
    ("Dragon Ribs", "龍", "三", "subtract"),
    ("Horse Cross", "馬", "十", "xor"),
    ("Fish Channels", "魚", "川", "subtract"),
    ("Bird Nest", "鳥", "田", "xor"),
    ("Door Mask", "戸", "工", "or"),
    ("Hand Cut", "手", "三", "subtract"),
    ("Eye Windows", "目", "十", "xor"),
    ("Heart Maze", "心", "二", "or"),
    ("Ship Decks", "舟", "三", "subtract"),
]


def find_glyph_font() -> str | None:
    """Find a local font that can render the glyph-based level recipes."""
    candidates = [
        Path("C:/Windows/Fonts/YuGothM.ttc"),
        Path("C:/Windows/Fonts/YuGothR.ttc"),
        Path("C:/Windows/Fonts/meiryo.ttc"),
        Path("C:/Windows/Fonts/msgothic.ttc"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/seguihis.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def generate_glyph_level(
    name: str,
    glyph: str,
    font_path: str,
    modifier_glyph: str | None = None,
    operation: str = "single",
) -> dict[str, list[str] | str]:
    """Convert one glyph recipe into a tile map with walls, spawn points, and enemies."""
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError("Pillow is required for glyph level generation")

    inner_cols = 23
    inner_rows = 16
    image_size = 640
    font = ImageFont.truetype(font_path, 520)
    base_mask = render_glyph_mask(glyph, font, image_size, inner_cols, inner_rows)
    if modifier_glyph is None:
        combined_mask = base_mask
    else:
        modifier_mask = render_glyph_mask(modifier_glyph, font, image_size, inner_cols, inner_rows)
        combined_mask = combine_glyph_masks(base_mask, modifier_mask, operation)

    rows: list[list[str]] = [["." for _ in range(25)] for _ in range(18)]
    rows[0] = ["#"] * 25
    rows[-1] = ["#"] * 25
    for row in rows:
        row[0] = "#"
        row[-1] = "#"

    for row_index in range(inner_rows):
        for col_index in range(inner_cols):
            if combined_mask[row_index][col_index]:
                rows[row_index + 1][col_index + 1] = "#"

    # Keep the outer floor/walls reliable and open enough for Bubble Bobble movement.
    for col in range(1, 24):
        rows[16][col] = "."
    for col in range(1, 24):
        rows[17][col] = "#"

    add_climbing_juts(rows, f"{glyph}{modifier_glyph or ''}{operation}")

    place_marker(rows, "P", preferred=[(15, 2), (15, 3), (14, 2), (14, 3)])
    for preferred in ([(12, 5), (11, 5)], [(12, 19), (11, 19)], [(8, 12), (9, 12)], [(6, 7), (6, 17)]):
        place_marker(rows, "W", preferred=preferred)
    for preferred in ([(2, 5), (2, 19)], [(3, 12)], [(4, 7), (4, 17)], [(5, 3), (5, 21)]):
        place_marker(rows, "A", preferred=preferred)

    glyph_label = glyph if modifier_glyph is None else f"{glyph} {operation} {modifier_glyph}"
    return {"name": name, "recipe": glyph_label, "rows": ["".join(row) for row in rows]}


def render_glyph_mask(glyph: str, font: object, image_size: int, cols: int, rows: int) -> list[list[bool]]:
    """Rasterize a glyph and sample it into the coarse level grid."""
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is required for glyph level generation")

    image = Image.new("L", (image_size, image_size), 0)
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((0, 0), glyph, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (image_size - text_width) / 2 - bbox[0]
    y = (image_size - text_height) / 2 - bbox[1]
    draw.text((x, y), glyph, fill=255, font=font)

    mask: list[list[bool]] = []
    for row_index in range(rows):
        mask_row = []
        for col_index in range(cols):
            left = col_index * image_size // cols
            top = row_index * image_size // rows
            right = (col_index + 1) * image_size // cols
            bottom = (row_index + 1) * image_size // rows
            tile = image.crop((left, top, right, bottom))
            density = sum(tile.getdata()) / (255 * tile.width * tile.height)
            mask_row.append(density > 0.16)
        mask.append(mask_row)
    return mask


def combine_glyph_masks(base: list[list[bool]], modifier: list[list[bool]], operation: str) -> list[list[bool]]:
    """Blend two glyph masks to create more varied wall silhouettes."""
    padded_modifier = dilate_mask(modifier)
    overlap = [[base_cell and modifier_cell for base_cell, modifier_cell in zip(base_row, modifier_row)] for base_row, modifier_row in zip(base, modifier)]
    padded_overlap = dilate_mask(overlap)

    combined: list[list[bool]] = []
    for base_row, modifier_row in zip(base, modifier):
        row = []
        row_index = len(combined)
        for col_index, (base_cell, modifier_cell) in enumerate(zip(base_row, modifier_row)):
            if operation == "or":
                row.append(base_cell or modifier_cell)
            elif operation == "xor":
                row.append((base_cell or modifier_cell) and not padded_overlap[row_index][col_index])
            elif operation == "subtract":
                row.append(base_cell and not padded_modifier[row_index][col_index])
            elif operation == "mask":
                row.append(base_cell and modifier_cell)
            else:
                row.append(base_cell)
        combined.append(row)

    solid_tiles = sum(cell for row in combined for cell in row)
    if solid_tiles < 24:
        # Some intersections are too sparse to play; fall back to a deterministic union.
        return combine_glyph_masks(base, modifier, "or")
    return combined


def dilate_mask(mask: list[list[bool]]) -> list[list[bool]]:
    """Thicken mask cells so generated platforms are playable instead of too sparse."""
    rows = len(mask)
    cols = len(mask[0]) if rows else 0
    dilated = [[False for _ in range(cols)] for _ in range(rows)]
    for row_index, row in enumerate(mask):
        for col_index, cell in enumerate(row):
            if not cell:
                continue
            for row_offset in (-1, 0, 1):
                for col_offset in (-1, 0, 1):
                    target_row = row_index + row_offset
                    target_col = col_index + col_offset
                    if 0 <= target_row < rows and 0 <= target_col < cols:
                        dilated[target_row][target_col] = True
    return dilated


def add_climbing_juts(rows: list[list[str]], glyph: str) -> None:
    """Add short ledges around vertical strokes so players and enemies can traverse maps."""
    rng = random.Random(glyph)
    jut_rows = list(range(13, 3, -3))
    vertical_cols = find_vertical_strokes(rows)

    if not vertical_cols:
        vertical_cols = [5, 9, 13, 17, 21]

    for index, row_index in enumerate(jut_rows):
        base_col = vertical_cols[index % len(vertical_cols)]
        side = -1 if index % 2 == 0 else 1
        if rng.random() < 0.35:
            side *= -1

        for length in (2, 1):
            if place_jut(rows, row_index, base_col, side, length):
                break

    # Add a few small freestanding stepping stones in large open gaps.
    for row_index in (14, 11, 8, 5):
        candidates = [
            col_index
            for col_index in range(3, 22)
            if rows[row_index][col_index] == "."
            and rows[row_index - 1][col_index] == "."
            and rows[row_index][col_index - 1] == "."
            and rows[row_index][col_index + 1] == "."
        ]
        rng.shuffle(candidates)
        for col_index in candidates[:1]:
            rows[row_index][col_index] = "#"

    add_vertical_access_steps(rows, rng)


def add_vertical_access_steps(rows: list[list[str]], rng: random.Random) -> None:
    """Create a rough ladder of reachable stepping stones from bottom to top."""
    previous_col = 4
    for row_index in (14, 12, 10, 8, 6, 4, 2):
        candidates = []
        for col_index in range(3, 22):
            if rows[row_index][col_index] != "." or rows[row_index - 1][col_index] != ".":
                continue
            distance = abs(col_index - previous_col)
            if distance <= 7:
                candidates.append((distance, col_index))

        if not candidates:
            candidates = [
                (abs(col_index - previous_col), col_index)
                for col_index in range(3, 22)
                if rows[row_index][col_index] == "." and rows[row_index - 1][col_index] == "."
            ]

        if not candidates:
            continue

        candidates.sort()
        close_candidates = [col for _distance, col in candidates[:6]]
        col_index = rng.choice(close_candidates)
        rows[row_index][col_index] = "#"
        if col_index + 1 < 23 and rows[row_index][col_index + 1] == "." and rng.random() < 0.55:
            rows[row_index][col_index + 1] = "#"
        previous_col = col_index


def find_vertical_strokes(rows: list[list[str]]) -> list[int]:
    """Find tall solid columns that are good anchors for generated ledges."""
    scored_cols: list[tuple[int, int]] = []
    for col_index in range(2, 23):
        longest_run = 0
        current_run = 0
        for row_index in range(1, 16):
            if rows[row_index][col_index] == "#":
                current_run += 1
                longest_run = max(longest_run, current_run)
            else:
                current_run = 0
        if longest_run >= 4:
            scored_cols.append((longest_run, col_index))

    scored_cols.sort(reverse=True)
    return [col_index for _score, col_index in scored_cols[:8]]


def place_jut(rows: list[list[str]], row_index: int, base_col: int, side: int, length: int) -> bool:
    """Try to place a short horizontal platform beside a glyph wall."""
    start_col = base_col + side
    end_col = start_col + side * length
    step = 1 if side > 0 else -1
    cols = list(range(start_col, end_col, step))

    if any(col <= 1 or col >= 23 for col in cols):
        return False
    if any(rows[row_index][col] != "." or rows[row_index - 1][col] != "." for col in cols):
        return False

    for col in cols:
        rows[row_index][col] = "#"
    return True


def place_marker(rows: list[list[str]], marker: str, preferred: list[tuple[int, int]]) -> None:
    """Place player, walking enemy, or airborne enemy markers in open spaces."""
    for row_index, col_index in preferred:
        if rows[row_index][col_index] == ".":
            rows[row_index][col_index] = marker
            return

    if marker == "A":
        for row_index in range(2, min(8, len(rows) - 2)):
            for col_index in range(2, len(rows[row_index]) - 2):
                if rows[row_index][col_index] == ".":
                    rows[row_index][col_index] = marker
                    return

    for row_index in range(len(rows) - 2, 1, -1):
        for col_index in range(2, len(rows[row_index]) - 2):
            if rows[row_index][col_index] == ".":
                rows[row_index][col_index] = marker
                return


def build_level_maps() -> list[dict[str, list[str] | str]]:
    """Use generated glyph maps when possible, otherwise fall back to hand-authored maps."""
    font_path = find_glyph_font()
    if font_path is None:
        return FALLBACK_LEVEL_MAPS

    try:
        return [
            generate_glyph_level(name, glyph, font_path, modifier_glyph, operation)
            for name, glyph, modifier_glyph, operation in GLYPH_LEVEL_SPECS
        ]
    except Exception:
        return FALLBACK_LEVEL_MAPS


LEVEL_MAPS = build_level_maps()


def stable_seed(*parts: object) -> int:
    """Create deterministic random seeds from level names and glyph recipes."""
    text = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


# Runtime entities share rectangle geometry for platform checks and overlap tests.
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
class Platform(Rect):
    pass


@dataclass
class Player(Rect):
    vx: float = 0
    vy: float = 0
    facing: int = 1
    on_ground: bool = False
    lives: int = 39
    cooldown: int = 0
    invincible_ticks: int = 0

    @property
    def collision_inset_x(self) -> float:
        return self.width * (1 - PLAYER_COLLISION_WIDTH_SCALE) / 2

    @property
    def left(self) -> float:
        return self.x + self.collision_inset_x

    @property
    def right(self) -> float:
        return self.x + self.width - self.collision_inset_x


@dataclass
class Enemy(Rect):
    vx: float
    vy: float = 0
    alive: bool = True
    trapped: bool = False
    on_ground: bool = False
    kind: str = "walker"


@dataclass
class Bubble(Rect):
    vx: float
    vy: float
    age: int = 0
    trapped_enemy: Enemy | None = None

    @property
    def has_enemy(self) -> bool:
        return self.trapped_enemy is not None


@dataclass
class Fruit(Rect):
    vy: float = 0
    value: int = 500


class BubbleBobbleGame:
    """Runs level loading, platform physics, bubble trapping, enemy behavior, scoring, and drawing."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tkinter Bubble Platformer")
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
        self.platforms: list[Platform] = []
        self.player = Player(80, 520, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.enemies: list[Enemy] = []
        self.bubbles: list[Bubble] = []
        self.fruits: list[Fruit] = []
        self.score = 0
        self.level = 1
        self.level_name = LEVEL_MAPS[0]["name"]
        self.player_start = (80.0, 520.0)
        self.game_over = False
        self.level_pause = 0
        self.after_id: str | None = None

        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.root.focus_set()

        self.restart()

    # Restart resets score and level progression, then loads the first map.
    def restart(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.keys.clear()
        self.score = 0
        self.level = 1
        self.game_over = False
        self.level_pause = 0
        self.player = Player(80, 520, PLAYER_WIDTH, PLAYER_HEIGHT)
        self.build_level()
        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    # Level maps are parsed from tile markers into platforms, player spawn, and enemies.
    def build_level(self) -> None:
        level_map = LEVEL_MAPS[(self.level - 1) % len(LEVEL_MAPS)]
        self.level_name = level_map["name"]
        rows = level_map["rows"]
        self.platforms = []
        player_spawn = (80.0, 520.0)
        walker_spawns: list[tuple[float, float]] = []
        air_spawns: list[tuple[float, float]] = []
        walker_candidates: list[tuple[float, float]] = []
        air_candidates: list[tuple[float, float]] = []

        for row_index, row in enumerate(rows):
            for col_index, marker in enumerate(row):
                x = MAP_X + col_index * TILE_SIZE
                y = MAP_Y + row_index * TILE_SIZE
                if marker == "#":
                    self.platforms.append(Platform(x, y, TILE_SIZE, TILE_SIZE))
                elif marker == "P":
                    player_spawn = (x + (TILE_SIZE - PLAYER_WIDTH) / 2, y + TILE_SIZE - PLAYER_HEIGHT)
                elif marker == "W":
                    walker_spawns.append((x + (TILE_SIZE - 34) / 2, y + TILE_SIZE - 34))
                elif marker == "A":
                    air_spawns.append((x + (TILE_SIZE - 32) / 2, y + (TILE_SIZE - 30) / 2))
                elif marker == ".":
                    if row_index < len(rows) - 1 and rows[row_index + 1][col_index] == "#":
                        walker_candidates.append((x + (TILE_SIZE - 34) / 2, y + TILE_SIZE - 34))
                    if row_index <= 8:
                        air_candidates.append((x + (TILE_SIZE - 32) / 2, y + (TILE_SIZE - 30) / 2))

        self.bubbles = []
        self.fruits = []
        self.player_start = player_spawn
        self.player.x = player_spawn[0]
        self.player.y = player_spawn[1]
        self.player.vx = 0
        self.player.vy = 0
        self.player.invincible_ticks = 90

        self.enemies = []
        spawn_rng = random.Random(stable_seed(self.level_name, self.level, "monster-spawns"))
        walker_pool = walker_spawns or walker_candidates
        air_pool = air_spawns or air_candidates
        spawn_rng.shuffle(walker_pool)
        spawn_rng.shuffle(air_pool)

        walker_count = min(2 + self.level, max(1, len(walker_pool)))
        for index in range(walker_count):
            x, y = walker_pool[index % len(walker_pool)]
            direction = spawn_rng.choice((-1, 1))
            self.enemies.append(Enemy(x, y, 34, 34, vx=direction * (ENEMY_SPEED + self.level * 0.12)))

        for index in range(self.level):
            x, y = air_pool[index % len(air_pool)]
            x += spawn_rng.choice((-10, 0, 10))
            y += spawn_rng.choice((-6, 0, 6))
            direction = 1 if self.player.center_x > x else -1
            self.enemies.append(
                Enemy(
                    x,
                    y,
                    32,
                    30,
                    vx=direction * (2.3 + min(self.level, 8) * 0.12),
                    vy=spawn_rng.choice((-1, 1)) * (1.7 + min(self.level, 8) * 0.08),
                    kind="airborne",
                )
            )

    # Input stores held keys; the frame loop applies movement, jumping, and bubble shots.
    def on_key_press(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        if key == "r":
            self.restart()
            return
        self.keys.add(key)

    def on_key_release(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym.lower())

    # One frame advances actors, bubbles, fruits, collisions, level state, and drawing.
    def update(self) -> None:
        self.after_id = None

        if not self.game_over:
            if self.level_pause > 0:
                self.level_pause -= 1
                if self.level_pause == 0:
                    self.level += 1
                    self.build_level()
            else:
                self.update_player()
                self.update_enemies()
                self.update_bubbles()
                self.update_fruits()
                self.handle_collisions()
                self.check_level_clear()

        self.draw()
        self.after_id = self.root.after(TICK_MS, self.update)

    def update_player(self) -> None:
        if self.player.cooldown > 0:
            self.player.cooldown -= 1
        if self.player.invincible_ticks > 0:
            self.player.invincible_ticks -= 1

        moving_left = "left" in self.keys or "a" in self.keys
        moving_right = "right" in self.keys or "d" in self.keys
        jumping = "up" in self.keys or "w" in self.keys
        blowing = "space" in self.keys or "z" in self.keys

        if moving_left and not moving_right:
            self.player.vx = -PLAYER_SPEED
            self.player.facing = -1
        elif moving_right and not moving_left:
            self.player.vx = PLAYER_SPEED
            self.player.facing = 1
        else:
            self.player.vx *= 0.72
            if abs(self.player.vx) < 0.12:
                self.player.vx = 0

        if jumping and self.player.on_ground:
            self.player.vy = JUMP_SPEED
            self.player.on_ground = False

        if blowing and self.player.cooldown == 0:
            self.shoot_bubble()
            self.player.cooldown = 24

        self.player.vy = min(self.player.vy + GRAVITY, MAX_PLAYER_FALL_SPEED)
        self.move_actor(self.player)

        if self.player.x < -self.player.width:
            self.player.x = SCREEN_WIDTH
        elif self.player.x > SCREEN_WIDTH:
            self.player.x = -self.player.width

    # Bubble shots are short-lived projectiles that can later trap enemies.
    def shoot_bubble(self) -> None:
        direction = self.player.facing
        x = self.player.center_x + direction * 22 - BUBBLE_SIZE / 2
        y = self.player.y + 8
        self.bubbles.append(Bubble(x, y, BUBBLE_SIZE, BUBBLE_SIZE, vx=direction * 5.4, vy=-0.7))

    # Enemy updates support both platform walkers and airborne chasers.
    def update_enemies(self) -> None:
        for enemy in self.enemies:
            if not enemy.alive or enemy.trapped:
                continue

            if enemy.kind == "airborne":
                self.update_airborne_enemy(enemy)
                continue

            enemy.vy += GRAVITY
            self.move_actor(enemy)

            if enemy.x < 20:
                enemy.x = 20
                enemy.vx = abs(enemy.vx)
            elif enemy.x + enemy.width > SCREEN_WIDTH - 20:
                enemy.x = SCREEN_WIDTH - enemy.width - 20
                enemy.vx = -abs(enemy.vx)

            if enemy.on_ground and random.random() < 0.006 + self.level * 0.001:
                enemy.vy = JUMP_SPEED * 0.82

    def update_airborne_enemy(self, enemy: Enemy) -> None:
        desired_direction = 1 if self.player.center_x > enemy.center_x else -1
        enemy.vx += desired_direction * 0.035
        max_speed = 2.9 + min(self.level, 8) * 0.12
        enemy.vx = max(-max_speed, min(enemy.vx, max_speed))

        if abs(enemy.vy) < 1.2:
            enemy.vy += random.choice((-1, 1)) * 0.12

        enemy.x += enemy.vx
        if enemy.left < 22:
            enemy.x = 22
            enemy.vx = abs(enemy.vx)
        elif enemy.right > SCREEN_WIDTH - 22:
            enemy.x = SCREEN_WIDTH - 22 - enemy.width
            enemy.vx = -abs(enemy.vx)

        enemy.y += enemy.vy
        if enemy.top < 72:
            enemy.y = 72
            enemy.vy = abs(enemy.vy)
        elif enemy.bottom > SCREEN_HEIGHT - 54:
            enemy.y = SCREEN_HEIGHT - 54 - enemy.height
            enemy.vy = -abs(enemy.vy)

        for platform in self.platforms:
            if not enemy.intersects(platform):
                continue

            horizontal_overlap = min(enemy.right - platform.left, platform.right - enemy.left)
            vertical_overlap = min(enemy.bottom - platform.top, platform.bottom - enemy.top)
            if horizontal_overlap < vertical_overlap:
                if enemy.center_x < platform.center_x:
                    enemy.x = platform.left - enemy.width
                    enemy.vx = -abs(enemy.vx)
                else:
                    enemy.x = platform.right
                    enemy.vx = abs(enemy.vx)
            else:
                if enemy.center_y < platform.center_y:
                    enemy.y = platform.top - enemy.height
                    enemy.vy = -abs(enemy.vy)
                else:
                    enemy.y = platform.bottom
                    enemy.vy = abs(enemy.vy)

    # Shared actor movement resolves horizontal and vertical platform collisions separately.
    def move_actor(self, actor: Player | Enemy) -> None:
        actor.x += actor.vx
        for platform in self.platforms:
            if actor.intersects(platform):
                if actor.vx > 0:
                    actor.x = platform.left - actor.width
                    if isinstance(actor, Enemy):
                        actor.vx = -abs(actor.vx)
                elif actor.vx < 0:
                    actor.x = platform.right
                    if isinstance(actor, Enemy):
                        actor.vx = abs(actor.vx)

        actor.y += actor.vy
        actor.on_ground = False
        for platform in self.platforms:
            if actor.intersects(platform):
                if actor.vy > 0:
                    actor.y = platform.top - actor.height
                    actor.vy = 0
                    actor.on_ground = True
                elif actor.vy < 0:
                    actor.y = platform.bottom
                    actor.vy = 0

    # Bubbles drift upward, hold trapped enemies for a limited time, then expire or release.
    def update_bubbles(self) -> None:
        remaining: list[Bubble] = []
        for bubble in self.bubbles:
            bubble.age += 1

            if bubble.has_enemy:
                bubble.vx *= 0.96
                bubble.vy = -1.45
            else:
                bubble.vx *= 0.985
                bubble.vy -= 0.012

            bubble.x += bubble.vx
            bubble.y += bubble.vy

            if bubble.x < 12 or bubble.x + bubble.width > SCREEN_WIDTH - 12:
                bubble.vx *= -1
            bubble.x = max(12, min(bubble.x, SCREEN_WIDTH - bubble.width - 12))

            if bubble.y < 65:
                bubble.vy = 0.6

            if bubble.has_enemy and bubble.age > 560:
                self.release_trapped_enemy(bubble)
                continue
            if not bubble.has_enemy and bubble.age > 185:
                continue

            remaining.append(bubble)

        self.bubbles = remaining

    def release_trapped_enemy(self, bubble: Bubble) -> None:
        enemy = bubble.trapped_enemy
        if enemy is None:
            return
        enemy.trapped = False
        enemy.x = bubble.x
        enemy.y = bubble.y
        if enemy.kind == "airborne":
            enemy.vx = random.choice((-1, 1)) * (2.4 + min(self.level, 8) * 0.12)
            enemy.vy = random.choice((-1, 1)) * (1.8 + min(self.level, 8) * 0.08)
        else:
            enemy.vy = -4
            enemy.vx = random.choice((-1, 1)) * (ENEMY_SPEED + self.level * 0.16)

    def update_fruits(self) -> None:
        for fruit in self.fruits:
            fruit.vy += GRAVITY
            fruit.y += fruit.vy
            for platform in self.platforms:
                if fruit.intersects(platform) and fruit.vy > 0:
                    fruit.y = platform.top - fruit.height
                    fruit.vy = 0

    # Collision handling covers trapping, popping, player damage, and fruit collection.
    def handle_collisions(self) -> None:
        self.handle_bubble_enemy_collisions()
        self.handle_bubble_pops()
        self.handle_player_enemy_collisions()
        self.handle_fruit_pickups()

    def handle_bubble_enemy_collisions(self) -> None:
        for bubble in self.bubbles:
            if bubble.has_enemy:
                continue
            for enemy in self.enemies:
                if enemy.alive and not enemy.trapped and bubble.intersects(enemy):
                    enemy.trapped = True
                    enemy.vx = 0
                    enemy.vy = 0
                    bubble.trapped_enemy = enemy
                    bubble.age = 0
                    bubble.vx = 0.8 * self.player.facing
                    bubble.vy = -1.2
                    bubble.x = enemy.center_x - bubble.width / 2
                    bubble.y = enemy.center_y - bubble.height / 2
                    break

    def handle_bubble_pops(self) -> None:
        remaining: list[Bubble] = []
        for bubble in self.bubbles:
            player_touches = bubble.intersects(self.player)
            old_trapped_bubble = bubble.has_enemy and bubble.age > 42
            if bubble.has_enemy and (player_touches or old_trapped_bubble and bubble.age > 390):
                self.pop_enemy_bubble(bubble)
            elif not bubble.has_enemy and player_touches and bubble.age > 20:
                self.score += 10
            else:
                remaining.append(bubble)
        self.bubbles = remaining

    def pop_enemy_bubble(self, bubble: Bubble) -> None:
        enemy = bubble.trapped_enemy
        if enemy is None:
            return
        enemy.alive = False
        enemy.trapped = False
        self.score += 1000
        self.fruits.append(Fruit(bubble.center_x - 12, bubble.center_y - 12, 24, 24, value=500 + self.level * 100))

    def handle_player_enemy_collisions(self) -> None:
        if self.player.invincible_ticks > 0:
            return

        for enemy in self.enemies:
            if enemy.alive and not enemy.trapped and self.player.intersects(enemy):
                self.damage_player()
                return

    def handle_fruit_pickups(self) -> None:
        remaining: list[Fruit] = []
        for fruit in self.fruits:
            if self.player.intersects(fruit):
                self.score += fruit.value
            else:
                remaining.append(fruit)
        self.fruits = remaining

    def damage_player(self) -> None:
        self.player.lives -= 1
        if self.player.lives <= 0:
            self.game_over = True
            return

        self.player.x = self.player_start[0]
        self.player.y = self.player_start[1]
        self.player.vx = 0
        self.player.vy = 0
        self.player.invincible_ticks = 120

    # Level progression waits briefly after all enemies are defeated.
    def check_level_clear(self) -> None:
        if self.enemies and all(not enemy.alive for enemy in self.enemies):
            self.level_pause = 110
            self.score += self.level * 1500

    # Rendering clears and rebuilds the whole scene from the current game state.
    def draw(self) -> None:
        self.canvas.delete("all")
        self.draw_background()
        self.draw_platforms()
        self.draw_fruits()
        self.draw_bubbles()
        self.draw_enemies()
        self.draw_player()
        self.draw_hud()

        if self.level_pause > 0:
            self.draw_center_banner("Round Clear!", f"Get ready for round {self.level + 1}")
        elif self.game_over:
            self.draw_center_banner("Game Over", "Press R to restart")

    def draw_background(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, fill=BACKGROUND, outline="")
        self.canvas.create_rectangle(0, 56, 18, SCREEN_HEIGHT, fill=WALL, outline="")
        self.canvas.create_rectangle(SCREEN_WIDTH - 18, 56, SCREEN_WIDTH, SCREEN_HEIGHT, fill=WALL, outline="")
        for y in range(92, SCREEN_HEIGHT, 80):
            for x in range(40, SCREEN_WIDTH, 90):
                self.canvas.create_oval(x, y, x + 4, y + 4, fill="#334155", outline="")

    def draw_platforms(self) -> None:
        for platform in self.platforms:
            self.canvas.create_rectangle(
                platform.x,
                platform.y,
                platform.x + platform.width,
                platform.y + platform.height,
                fill=PLATFORM,
                outline=PLATFORM_DARK,
                width=2,
            )
            self.canvas.create_line(platform.x + 5, platform.y + 5, platform.x + platform.width - 5, platform.y + 5, fill="#99f6e4", width=1)
            self.canvas.create_line(platform.x + 5, platform.y + platform.height - 5, platform.x + platform.width - 5, platform.y + platform.height - 5, fill=PLATFORM_DARK, width=1)

    def draw_player(self) -> None:
        if self.player.invincible_ticks and (self.player.invincible_ticks // 6) % 2 == 0:
            return

        x = self.player.x
        y = self.player.y
        self.canvas.create_oval(x, y + 3, x + self.player.width, y + self.player.height, fill=PLAYER, outline=PLAYER_DARK, width=2)
        self.canvas.create_oval(x + 8, y + 17, x + 23, y + 29, fill=PLAYER_BELLY, outline="")
        self.canvas.create_oval(x + 8, y + 11, x + 13, y + 16, fill="#020617", outline="")
        self.canvas.create_oval(x + 19, y + 11, x + 24, y + 16, fill="#020617", outline="")

        if self.player.facing > 0:
            self.canvas.create_polygon(x + 21, y + 7, x + 31, y, x + 28, y + 13, fill=PLAYER, outline=PLAYER_DARK)
        else:
            self.canvas.create_polygon(x + 9, y + 7, x - 1, y, x + 2, y + 13, fill=PLAYER, outline=PLAYER_DARK)
        self.canvas.create_rectangle(x + 5, y + 25, x + 13, y + 30, fill=PLAYER_DARK, outline="")
        self.canvas.create_rectangle(x + 18, y + 25, x + 26, y + 30, fill=PLAYER_DARK, outline="")

    def draw_enemies(self) -> None:
        for enemy in self.enemies:
            if not enemy.alive or enemy.trapped:
                continue
            x = enemy.x
            y = enemy.y
            if enemy.kind == "airborne":
                self.canvas.create_oval(x, y, x + enemy.width, y + enemy.height, fill=AIR_ENEMY, outline=AIR_ENEMY_DARK, width=2)
                self.canvas.create_polygon(x - 9, y + 15, x + 6, y + 5, x + 7, y + 24, fill=AIR_ENEMY, outline=AIR_ENEMY_DARK)
                self.canvas.create_polygon(x + enemy.width + 9, y + 15, x + enemy.width - 6, y + 5, x + enemy.width - 7, y + 24, fill=AIR_ENEMY, outline=AIR_ENEMY_DARK)
                self.canvas.create_oval(x + 9, y + 10, x + 14, y + 15, fill="#020617", outline="")
                self.canvas.create_oval(x + 20, y + 10, x + 25, y + 15, fill="#020617", outline="")
            else:
                self.canvas.create_oval(x, y, x + enemy.width, y + enemy.height, fill=ENEMY, outline=ENEMY_DARK, width=2)
                self.canvas.create_polygon(x + 7, y + 5, x + 2, y - 7, x + 16, y + 1, fill=ENEMY, outline=ENEMY_DARK)
                self.canvas.create_polygon(x + 27, y + 5, x + 34, y - 7, x + 20, y + 1, fill=ENEMY, outline=ENEMY_DARK)
                self.canvas.create_oval(x + 9, y + 12, x + 14, y + 17, fill="#020617", outline="")
                self.canvas.create_oval(x + 22, y + 12, x + 27, y + 17, fill="#020617", outline="")

    def draw_bubbles(self) -> None:
        for bubble in self.bubbles:
            fill = "#dbeafe" if bubble.has_enemy else BUBBLE
            outline = ACCENT if bubble.has_enemy else BUBBLE_EDGE
            self.canvas.create_oval(bubble.x, bubble.y, bubble.x + bubble.width, bubble.y + bubble.height, fill=fill, outline=outline, width=2)
            self.canvas.create_oval(bubble.x + 8, bubble.y + 7, bubble.x + 15, bubble.y + 14, fill="#ffffff", outline="")

            if bubble.has_enemy:
                enemy = bubble.trapped_enemy
                if enemy is not None:
                    fill = AIR_ENEMY if enemy.kind == "airborne" else ENEMY
                    outline = AIR_ENEMY_DARK if enemy.kind == "airborne" else ENEMY_DARK
                    self.canvas.create_oval(bubble.x + 9, bubble.y + 10, bubble.x + 25, bubble.y + 27, fill=fill, outline=outline)

    def draw_fruits(self) -> None:
        for fruit in self.fruits:
            self.canvas.create_oval(fruit.x, fruit.y + 5, fruit.x + fruit.width, fruit.y + fruit.height, fill=FRUIT, outline="#be123c", width=2)
            self.canvas.create_line(fruit.center_x, fruit.y + 7, fruit.center_x + 8, fruit.y, fill="#22c55e", width=2)

    def draw_hud(self) -> None:
        self.canvas.create_rectangle(0, 0, SCREEN_WIDTH, 56, fill=PANEL, outline="#1e293b")
        self.canvas.create_text(
            18,
            28,
            text=f"Score: {self.score}    Lives: {self.player.lives}    Round: {self.level} - {self.level_name}",
            anchor="w",
            fill=TEXT,
            font=("Segoe UI", 14, "bold"),
        )
        self.canvas.create_text(
            SCREEN_WIDTH - 18,
            28,
            text="Move: A/D or arrows   Jump: W/Up   Bubble: Space/Z   Restart: R",
            anchor="e",
            fill=MUTED,
            font=("Segoe UI", 10),
        )

    def draw_center_banner(self, title: str, subtitle: str) -> None:
        self.canvas.create_rectangle(225, 250, 595, 385, fill=PANEL, outline=ACCENT, width=3)
        self.canvas.create_text(SCREEN_WIDTH / 2, 294, text=title, fill=TEXT, font=("Segoe UI", 27, "bold"))
        self.canvas.create_text(SCREEN_WIDTH / 2, 336, text=subtitle, fill=MUTED, font=("Segoe UI", 13))


def main() -> None:
    """Create the Tkinter root and hand control to Tkinter's event loop."""
    root = tk.Tk()
    try:
        root.iconname("Tkinter Bubble Platformer")
    except tk.TclError:
        pass

    BubbleBobbleGame(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except tk.TclError as exc:
        messagebox.showerror("Tkinter Bubble Platformer", f"Could not start Tkinter: {exc}")
