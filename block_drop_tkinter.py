"""A complete falling-block puzzle game implemented with the Python standard-library Tkinter UI."""

from __future__ import annotations

import random
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox


# Board sizing, timing, and color constants keep the rest of the game logic readable.
BOARD_WIDTH = 10
BOARD_HEIGHT = 20
CELL_SIZE = 30
SIDE_PANEL_WIDTH = 180
START_DELAY_MS = 650

BACKGROUND = "#111827"
GRID_COLOR = "#1f2937"
TEXT_COLOR = "#f9fafb"
MUTED_TEXT = "#cbd5e1"
ACCENT = "#0f766e"
PREVIEW_BG = "#0f172a"
LOCKED_BORDER = "#020617"

# Tetromino definitions are stored as local block offsets plus a display color.
SHAPES = {
    "I": {
        "color": "#06b6d4",
        "blocks": [(0, 1), (1, 1), (2, 1), (3, 1)],
    },
    "J": {
        "color": "#2563eb",
        "blocks": [(0, 0), (0, 1), (1, 1), (2, 1)],
    },
    "L": {
        "color": "#f97316",
        "blocks": [(2, 0), (0, 1), (1, 1), (2, 1)],
    },
    "O": {
        "color": "#eab308",
        "blocks": [(1, 0), (2, 0), (1, 1), (2, 1)],
    },
    "S": {
        "color": "#22c55e",
        "blocks": [(1, 0), (2, 0), (0, 1), (1, 1)],
    },
    "T": {
        "color": "#a855f7",
        "blocks": [(1, 0), (0, 1), (1, 1), (2, 1)],
    },
    "Z": {
        "color": "#ef4444",
        "blocks": [(0, 0), (1, 0), (1, 1), (2, 1)],
    },
}

LINE_SCORES = {1: 100, 2: 300, 3: 500, 4: 800}


@dataclass
class Piece:
    """Current falling piece in board coordinates."""

    kind: str
    blocks: list[tuple[int, int]]
    color: str
    x: int = 3
    y: int = 0

    @classmethod
    def random(cls) -> "Piece":
        kind = random.choice(list(SHAPES))
        shape = SHAPES[kind]
        return cls(kind=kind, blocks=list(shape["blocks"]), color=shape["color"])

    def cells(self, x_offset: int = 0, y_offset: int = 0) -> list[tuple[int, int]]:
        return [(self.x + x + x_offset, self.y + y + y_offset) for x, y in self.blocks]

    def rotated_blocks(self) -> list[tuple[int, int]]:
        if self.kind == "O":
            return list(self.blocks)

        rotated = [(y, -x) for x, y in self.blocks]
        min_x = min(x for x, _ in rotated)
        min_y = min(y for _, y in rotated)
        return [(x - min_x, y - min_y) for x, y in rotated]


class BlockDropGame:
    """Owns the Tkinter UI, game state, input bindings, update loop, and drawing."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tkinter Block Drop")
        self.root.resizable(False, False)

        width = BOARD_WIDTH * CELL_SIZE + SIDE_PANEL_WIDTH
        height = BOARD_HEIGHT * CELL_SIZE
        self.canvas = tk.Canvas(
            root,
            width=width,
            height=height,
            bg=BACKGROUND,
            highlightthickness=0,
        )
        self.canvas.pack()

        self.board: list[list[str | None]] = []
        self.current_piece = Piece.random()
        self.next_piece = Piece.random()
        self.score = 0
        self.lines = 0
        self.level = 1
        self.game_over = False
        self.paused = False
        self.after_id: str | None = None

        self.root.bind("<Left>", lambda _event: self.move(-1, 0))
        self.root.bind("<Right>", lambda _event: self.move(1, 0))
        self.root.bind("<Down>", lambda _event: self.soft_drop())
        self.root.bind("<Up>", lambda _event: self.rotate())
        self.root.bind("<space>", lambda _event: self.hard_drop())
        self.root.bind("p", lambda _event: self.toggle_pause())
        self.root.bind("P", lambda _event: self.toggle_pause())
        self.root.bind("r", lambda _event: self.restart())
        self.root.bind("R", lambda _event: self.restart())

        self.restart()

    # Game lifecycle resets board state and keeps the Tkinter timer from duplicating.
    def restart(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.board = [[None for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]
        self.current_piece = Piece.random()
        self.next_piece = Piece.random()
        self.score = 0
        self.lines = 0
        self.level = 1
        self.game_over = False
        self.paused = False
        self.draw()
        self.schedule_tick()

    # The falling loop speeds up with the level and reschedules itself with root.after.
    def schedule_tick(self) -> None:
        if not self.game_over and not self.paused:
            self.after_id = self.root.after(self.fall_delay_ms(), self.tick)

    def fall_delay_ms(self) -> int:
        return max(90, START_DELAY_MS - (self.level - 1) * 45)

    def tick(self) -> None:
        self.after_id = None
        if not self.move(0, 1):
            self.lock_piece()
            self.clear_lines()
            self.spawn_piece()
        self.draw()
        self.schedule_tick()

    # Player actions try a state change first, then redraw only when the move is valid.
    def move(self, dx: int, dy: int) -> bool:
        if self.game_over or self.paused:
            return False

        if self.is_valid_position(self.current_piece, dx, dy):
            self.current_piece.x += dx
            self.current_piece.y += dy
            self.draw()
            return True
        return False

    def soft_drop(self) -> None:
        if self.move(0, 1):
            self.score += 1
            self.draw()

    def hard_drop(self) -> None:
        if self.game_over or self.paused:
            return

        dropped_rows = 0
        while self.is_valid_position(self.current_piece, 0, 1):
            self.current_piece.y += 1
            dropped_rows += 1

        self.score += dropped_rows * 2
        self.lock_piece()
        self.clear_lines()
        self.spawn_piece()
        self.draw()

    def rotate(self) -> None:
        if self.game_over or self.paused:
            return

        original_blocks = self.current_piece.blocks
        self.current_piece.blocks = self.current_piece.rotated_blocks()

        # Small wall kicks make rotation feel natural near edges.
        for kick in (0, -1, 1, -2, 2):
            if self.is_valid_position(self.current_piece, kick, 0):
                self.current_piece.x += kick
                self.draw()
                return

        self.current_piece.blocks = original_blocks

    def toggle_pause(self) -> None:
        if self.game_over:
            return

        self.paused = not self.paused
        if self.paused and self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        elif not self.paused:
            self.schedule_tick()
        self.draw()

    # Collision checks are the central rule gate for movement, rotation, and spawning.
    def is_valid_position(self, piece: Piece, dx: int = 0, dy: int = 0) -> bool:
        for x, y in piece.cells(dx, dy):
            if x < 0 or x >= BOARD_WIDTH or y >= BOARD_HEIGHT:
                return False
            if y >= 0 and self.board[y][x] is not None:
                return False
        return True

    # Locking transfers the falling piece into the board, clears lines, then spawns next.
    def lock_piece(self) -> None:
        for x, y in self.current_piece.cells():
            if y < 0:
                self.end_game()
                return
            self.board[y][x] = self.current_piece.color

    def clear_lines(self) -> None:
        remaining_rows = [row for row in self.board if any(cell is None for cell in row)]
        cleared = BOARD_HEIGHT - len(remaining_rows)

        if cleared:
            empty_rows = [[None for _ in range(BOARD_WIDTH)] for _ in range(cleared)]
            self.board = empty_rows + remaining_rows
            self.lines += cleared
            self.level = self.lines // 10 + 1
            self.score += LINE_SCORES[cleared] * self.level

    def spawn_piece(self) -> None:
        if self.game_over:
            return

        self.current_piece = self.next_piece
        self.current_piece.x = 3
        self.current_piece.y = 0
        self.next_piece = Piece.random()

        if not self.is_valid_position(self.current_piece):
            self.end_game()

    def end_game(self) -> None:
        self.game_over = True
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    # Rendering is rebuilt from state each frame instead of mutating previous canvas items.
    def draw(self) -> None:
        self.canvas.delete("all")
        self.draw_board_background()
        self.draw_locked_blocks()
        if not self.game_over:
            self.draw_piece(self.current_piece)
        self.draw_side_panel()

        if self.paused:
            self.draw_center_text("Paused", "Press P to resume")
        elif self.game_over:
            self.draw_center_text("Game Over", "Press R to restart")

    def draw_board_background(self) -> None:
        board_pixel_width = BOARD_WIDTH * CELL_SIZE
        board_pixel_height = BOARD_HEIGHT * CELL_SIZE

        self.canvas.create_rectangle(
            0,
            0,
            board_pixel_width,
            board_pixel_height,
            fill=BACKGROUND,
            outline=GRID_COLOR,
            width=2,
        )

        for x in range(BOARD_WIDTH + 1):
            pixel_x = x * CELL_SIZE
            self.canvas.create_line(pixel_x, 0, pixel_x, board_pixel_height, fill=GRID_COLOR)

        for y in range(BOARD_HEIGHT + 1):
            pixel_y = y * CELL_SIZE
            self.canvas.create_line(0, pixel_y, board_pixel_width, pixel_y, fill=GRID_COLOR)

    def draw_locked_blocks(self) -> None:
        for y, row in enumerate(self.board):
            for x, color in enumerate(row):
                if color is not None:
                    self.draw_block(x, y, color)

    def draw_piece(self, piece: Piece) -> None:
        for x, y in piece.cells():
            if y >= 0:
                self.draw_block(x, y, piece.color)

    def draw_block(self, x: int, y: int, color: str) -> None:
        x1 = x * CELL_SIZE
        y1 = y * CELL_SIZE
        x2 = x1 + CELL_SIZE
        y2 = y1 + CELL_SIZE

        self.canvas.create_rectangle(x1 + 1, y1 + 1, x2 - 1, y2 - 1, fill=color, outline=LOCKED_BORDER)
        self.canvas.create_line(x1 + 3, y1 + 3, x2 - 4, y1 + 3, fill="#ffffff", width=1)

    def draw_side_panel(self) -> None:
        panel_x = BOARD_WIDTH * CELL_SIZE
        self.canvas.create_rectangle(
            panel_x,
            0,
            panel_x + SIDE_PANEL_WIDTH,
            BOARD_HEIGHT * CELL_SIZE,
            fill="#0b1220",
            outline="",
        )

        self.canvas.create_text(
            panel_x + 22,
            34,
            text="BLOCK DROP",
            anchor="w",
            fill=TEXT_COLOR,
            font=("Segoe UI", 22, "bold"),
        )
        self.draw_stat("Score", self.score, panel_x, 88)
        self.draw_stat("Lines", self.lines, panel_x, 142)
        self.draw_stat("Level", self.level, panel_x, 196)

        self.canvas.create_text(
            panel_x + 22,
            260,
            text="Next",
            anchor="w",
            fill=TEXT_COLOR,
            font=("Segoe UI", 14, "bold"),
        )
        self.draw_next_piece(panel_x + 22, 286)

        controls = [
            "Controls",
            "Left / Right: move",
            "Down: soft drop",
            "Up: rotate",
            "Space: hard drop",
            "P: pause",
            "R: restart",
        ]
        y = 420
        for index, label in enumerate(controls):
            font = ("Segoe UI", 11, "bold") if index == 0 else ("Segoe UI", 9)
            fill = TEXT_COLOR if index == 0 else MUTED_TEXT
            self.canvas.create_text(panel_x + 22, y, text=label, anchor="w", fill=fill, font=font)
            y += 24 if index == 0 else 20

    def draw_stat(self, label: str, value: int, panel_x: int, y: int) -> None:
        self.canvas.create_text(
            panel_x + 22,
            y,
            text=label,
            anchor="w",
            fill=MUTED_TEXT,
            font=("Segoe UI", 10),
        )
        self.canvas.create_text(
            panel_x + 22,
            y + 24,
            text=str(value),
            anchor="w",
            fill=TEXT_COLOR,
            font=("Segoe UI", 18, "bold"),
        )

    def draw_next_piece(self, x: int, y: int) -> None:
        preview_size = CELL_SIZE * 4
        self.canvas.create_rectangle(
            x,
            y,
            x + preview_size,
            y + preview_size,
            fill=PREVIEW_BG,
            outline=GRID_COLOR,
        )

        blocks = self.next_piece.blocks
        min_x = min(block_x for block_x, _ in blocks)
        max_x = max(block_x for block_x, _ in blocks)
        min_y = min(block_y for _, block_y in blocks)
        max_y = max(block_y for _, block_y in blocks)
        shape_width = (max_x - min_x + 1) * CELL_SIZE
        shape_height = (max_y - min_y + 1) * CELL_SIZE
        offset_x = x + (preview_size - shape_width) // 2 - min_x * CELL_SIZE
        offset_y = y + (preview_size - shape_height) // 2 - min_y * CELL_SIZE

        for block_x, block_y in blocks:
            x1 = offset_x + block_x * CELL_SIZE
            y1 = offset_y + block_y * CELL_SIZE
            self.canvas.create_rectangle(
                x1 + 1,
                y1 + 1,
                x1 + CELL_SIZE - 1,
                y1 + CELL_SIZE - 1,
                fill=self.next_piece.color,
                outline=LOCKED_BORDER,
            )

    def draw_center_text(self, title: str, subtitle: str) -> None:
        board_pixel_width = BOARD_WIDTH * CELL_SIZE
        board_pixel_height = BOARD_HEIGHT * CELL_SIZE
        center_x = board_pixel_width // 2
        center_y = board_pixel_height // 2

        self.canvas.create_rectangle(
            32,
            center_y - 66,
            board_pixel_width - 32,
            center_y + 66,
            fill="#020617",
            outline=ACCENT,
            width=2,
        )
        self.canvas.create_text(
            center_x,
            center_y - 18,
            text=title,
            fill=TEXT_COLOR,
            font=("Segoe UI", 24, "bold"),
        )
        self.canvas.create_text(
            center_x,
            center_y + 24,
            text=subtitle,
            fill=MUTED_TEXT,
            font=("Segoe UI", 12),
        )


def main() -> None:
    """Create the Tkinter root and hand control to Tkinter's event loop."""
    root = tk.Tk()
    try:
        root.iconname("Tkinter Block Drop")
    except tk.TclError:
        pass

    BlockDropGame(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except tk.TclError as exc:
        messagebox.showerror("Tkinter Block Drop", f"Could not start Tkinter: {exc}")
