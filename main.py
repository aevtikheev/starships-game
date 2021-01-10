import asyncio
import curses
import time
import random
import os

TIC_TIMEOUT = 0.1

SPACE_KEY_CODE = 32
LEFT_KEY_CODE = 260
RIGHT_KEY_CODE = 261
UP_KEY_CODE = 259
DOWN_KEY_CODE = 258

FRAMES_FOLDER = 'frames'
ROCKET_FRAME_FILES = ('rocket_frame_1.txt', 'rocket_frame_2.txt')

BORDER_LENGTH = 1


async def draw_star(canvas, row, column, symbol='*', offset_tics=0):
    tics_bold = 5
    tics_dim = 20
    tics_before_bold = 3
    tics_after_bold = 3

    for _ in range(offset_tics):
        canvas.addstr(row, column, symbol, curses.A_DIM)
        await asyncio.sleep(0)
    while True:
        for _ in range(tics_before_bold):
            canvas.addstr(row, column, symbol)
            await asyncio.sleep(0)
        for _ in range(tics_bold):
            canvas.addstr(row, column, symbol, curses.A_BOLD)
            await asyncio.sleep(0)
        for _ in range(tics_after_bold):
            canvas.addstr(row, column, symbol)
            await asyncio.sleep(0)
        for _ in range(tics_dim):
            canvas.addstr(row, column, symbol, curses.A_DIM)
            await asyncio.sleep(0)


def create_stars(canvas, count):
    star_size = 1
    max_rows, max_columns = (max_coordinate - star_size - BORDER_LENGTH for max_coordinate in canvas.getmaxyx())
    min_rows = min_columns = BORDER_LENGTH

    coroutines = []
    for _ in range(count):
        row = random.randint(min_rows, max_rows)
        column = random.randint(min_columns, max_columns)
        symbol = random.choice('+*.:')
        offset_blink = random.randint(1, 20)
        coroutines.append(draw_star(canvas, row, column, symbol, offset_blink))
    return coroutines


async def draw_fire(canvas, start_row, start_column, rows_speed=-0.3, columns_speed=0):
    """Display animation of gun shot. Direction and speed can be specified."""
    row, column = start_row, start_column

    canvas.addstr(round(row), round(column), '*')
    await asyncio.sleep(0)

    canvas.addstr(round(row), round(column), 'O')
    await asyncio.sleep(0)
    canvas.addstr(round(row), round(column), ' ')

    row += rows_speed
    column += columns_speed

    symbol = '-' if columns_speed else '|'

    rows, columns = canvas.getmaxyx()
    max_row, max_column = rows - BORDER_LENGTH, columns - BORDER_LENGTH

    curses.beep()

    while 0 < row < max_row and 0 < column < max_column:
        canvas.addstr(round(row), round(column), symbol)
        await asyncio.sleep(0)
        canvas.addstr(round(row), round(column), ' ')
        row += rows_speed
        column += columns_speed


async def draw_spaceship(canvas, start_row, start_column, spaceship_frames):
    """Display animation of a spaceship."""
    tics_between_animations = 3

    max_rows, max_columns = (x - BORDER_LENGTH for x in canvas.getmaxyx())
    min_rows = min_columns = BORDER_LENGTH

    row, column = start_row, start_column
    while True:
        rows_direction, columns_direction, _ = read_controls(canvas)
        row = row + rows_direction
        column = column + columns_direction
        for spaceship_frame in spaceship_frames:
            spaceship_size_rows, spaceship_size_columns = get_frame_size(spaceship_frame)
            row = max(row, min_rows)
            row = min(row, max_rows - spaceship_size_rows)
            column = max(column, min_columns)
            column = min(column, max_columns - spaceship_size_columns)
            for _ in range(tics_between_animations):
                draw_frame(canvas, row, column, spaceship_frame)
                await asyncio.sleep(0)
                draw_frame(canvas, row, column, spaceship_frame, negative=True)


def read_controls(canvas):
    """Read keys pressed and returns tuple with controls state."""

    rows_direction = columns_direction = 0
    space_pressed = False

    while True:
        pressed_key_code = canvas.getch()

        if pressed_key_code == -1:
            # https://docs.python.org/3/library/curses.html#curses.window.getch
            break

        if pressed_key_code == UP_KEY_CODE:
            rows_direction = -1

        if pressed_key_code == DOWN_KEY_CODE:
            rows_direction = 1

        if pressed_key_code == RIGHT_KEY_CODE:
            columns_direction = 1

        if pressed_key_code == LEFT_KEY_CODE:
            columns_direction = -1

        if pressed_key_code == SPACE_KEY_CODE:
            space_pressed = True

    return rows_direction, columns_direction, space_pressed


def draw_frame(canvas, start_row, start_column, text, negative=False):
    """Draw multiline text fragment on canvas. Erase text instead of drawing if negative=True is specified."""

    rows_number, columns_number = canvas.getmaxyx()

    for row, line in enumerate(text.splitlines(), round(start_row)):
        if row < 0:
            continue

        if row >= rows_number:
            break

        for column, symbol in enumerate(line, round(start_column)):
            if column < 0:
                continue

            if column >= columns_number:
                break

            if symbol == ' ':
                continue

            # Check that current position it is not in a lower right corner of the window
            # Curses will raise exception in that case. Don`t ask why…
            # https://docs.python.org/3/library/curses.html#curses.window.addch
            if row == rows_number - 1 and column == columns_number - 1:
                continue

            symbol = symbol if not negative else ' '
            canvas.addch(row, column, symbol)


def get_frame_size(text):
    """Calculate size of multiline text fragment. Returns pair (rows number, colums number)"""
    lines = text.splitlines()
    rows = len(lines)
    columns = max([len(line) for line in lines])

    return rows, columns


def read_spaceship_frames(frame_file_paths):
    frames = []
    for frame_file_path in frame_file_paths:
        with open(frame_file_path, 'r') as frame_file:
            frames.append(frame_file.read())
    return frames


def main(canvas):
    rocket_frames = read_spaceship_frames(
        os.path.join(FRAMES_FOLDER, f) for f in ROCKET_FRAME_FILES
    )
    canvas.border()
    canvas.nodelay(True)
    curses.curs_set(0)
    coroutines = create_stars(canvas, count=100)
    central_row, central_column = (x//2 for x in canvas.getmaxyx())
    coroutines.append(draw_fire(canvas, start_row=central_row, start_column=central_column))
    coroutines.append(draw_spaceship(canvas=canvas, start_row=central_row,
                                     start_column=central_column, spaceship_frames=rocket_frames))
    while True:
        for coroutine in coroutines:
            try:
                coroutine.send(None)
            except StopIteration:
                coroutines.remove(coroutine)
        canvas.refresh()
        time.sleep(TIC_TIMEOUT)


if __name__ == '__main__':
    curses.update_lines_cols()
    curses.wrapper(main)
