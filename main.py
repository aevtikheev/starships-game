import asyncio
import curses
import time
import random
import os
import itertools

from tools import get_frame_size, draw_frame, read_frames, read_controls
from physics import update_speed
from obstacles import Obstacle, show_obstacles
from explosion import explode
from game_scenario import PHRASES, get_garbage_delay_tics


TIC_TIMEOUT = 0.1
TICS_PER_YEAR = 20

FRAMES_FOLDER = 'frames'
SPACESHIP_FRAMES_FOLDER = os.path.join(FRAMES_FOLDER, 'spaceship')
GARBAGE_FRAMES_FOLDER = os.path.join(FRAMES_FOLDER, 'garbage')
GAME_OVER_FRAME_FILE = os.path.join(FRAMES_FOLDER, 'game_over.txt')

BORDER_LENGTH = 1
CAPTION_WINDOW_LENGTH_PART = 3  # x means that caption window length is 1/x of the screen length.

GUN_AVAILABLE_YEAR = 2020

SHOW_OBSTACLES = False


coroutines = []
obstacles = []
obstacles_in_last_collisions = []
year = 1957


async def sleep(tics=1):
    """Do nothing for a specified amount of tics."""
    for _ in range(tics):
        await asyncio.sleep(0)


async def show_caption(canvas):
    """Show scenario text in the bottom of the screen."""
    global year

    max_rows, max_columns = canvas.getmaxyx()
    caption_window_nlines = 1 + BORDER_LENGTH * 2
    caption_window_ncols = max_columns // CAPTION_WINDOW_LENGTH_PART
    caption_window_begin_y = max_rows - BORDER_LENGTH - caption_window_nlines
    caption_window_begin_x = max_columns // 2 - caption_window_ncols // 2

    caption_window = canvas.derwin(
        caption_window_nlines,
        caption_window_ncols,
        caption_window_begin_y,
        caption_window_begin_x,
    )

    while True:
        caption_text = f'Year {year}'
        if year in PHRASES:
            caption_text = caption_text + '. ' + PHRASES[year]

        caption_row = 1
        caption_column = caption_window_ncols // 2 - len(caption_text) // 2

        draw_frame(caption_window, caption_row, caption_column, caption_text)
        await sleep()
        draw_frame(caption_window, caption_row, caption_column, caption_text, negative=True)


async def handle_year(tics_per_year):
    """Increase the game's year after a specified amount of tics."""
    global year
    while True:
        await sleep(tics_per_year)
        year += 1


async def draw_star(canvas, row, column, symbol='*', offset_tics=0):
    """Draw a single star."""
    tics_bold = 5
    tics_dim = 20
    tics_before_bold = 3
    tics_after_bold = 3

    canvas.addstr(row, column, symbol, curses.A_DIM)
    await sleep(offset_tics)

    while True:
        canvas.addstr(row, column, symbol)
        await sleep(tics_before_bold)
        canvas.addstr(row, column, symbol, curses.A_BOLD)
        await sleep(tics_bold)
        canvas.addstr(row, column, symbol)
        await sleep(tics_after_bold)
        canvas.addstr(row, column, symbol, curses.A_DIM)
        await sleep(tics_dim)


def create_stars(canvas, count):
    """Fill the screen with a specified amount of stars."""
    star_size = 1
    max_rows, max_columns = (
        max_coordinate - star_size - BORDER_LENGTH for max_coordinate in canvas.getmaxyx()
    )
    min_rows = min_columns = BORDER_LENGTH

    global coroutines
    for _ in range(count):
        row = random.randint(min_rows, max_rows)
        column = random.randint(min_columns, max_columns)
        symbol = random.choice('+*.:')
        offset_blink = random.randint(1, 20)
        coroutines.append(draw_star(canvas, row, column, symbol, offset_blink))


async def fill_orbit_with_garbage(canvas):
    """Fill screen with garbage. Garbage amount slowly increases by time."""
    garbage_frame_files = [
        os.path.join(GARBAGE_FRAMES_FOLDER, file) for file in os.listdir(GARBAGE_FRAMES_FOLDER)
    ]
    garbage_frames = read_frames(garbage_frame_files)

    global coroutines
    global year

    while True:
        delay_tics = get_garbage_delay_tics(year)
        if delay_tics is not None:
            coroutines.append(
                fly_garbage(
                    canvas=canvas,
                    column=random.randint(0, canvas.getmaxyx()[1]),
                    garbage_frame=random.choice(garbage_frames)
                )
            )
            await sleep(delay_tics)
        else:
            await sleep()


async def fly_garbage(canvas, column, garbage_frame, speed=0.5):
    """Animate garbage, flying from top to bottom. Сolumn position will stay same, as specified on start."""
    rows_number, columns_number = canvas.getmaxyx()
    column = max(column, 0)
    column = min(column, columns_number - 1)
    row = 0

    garbage_frame_size_rows, garbage_frame_size_columns = get_frame_size(garbage_frame)
    obstacle = Obstacle(row, column, garbage_frame_size_rows, garbage_frame_size_columns)
    obstacles.append(obstacle)

    try:
        while row < rows_number:
            obstacle.row = row
            draw_frame(canvas, row, column, garbage_frame)
            await sleep()
            draw_frame(canvas, row, column, garbage_frame, negative=True)
            row += speed

            if obstacle in obstacles_in_last_collisions:
                obstacles_in_last_collisions.remove(obstacle)
                garbage_frame_center_row = row + garbage_frame_size_rows // 2
                garbage_frame_center_column = column + garbage_frame_size_columns // 2
                await explode(canvas, garbage_frame_center_row, garbage_frame_center_column)
                return
    finally:
        obstacles.remove(obstacle)


async def draw_fire(canvas, start_row, start_column, rows_speed=-0.3, columns_speed=0):
    """Display animation of gun shot. Direction and speed can be specified."""
    row, column = start_row, start_column

    canvas.addstr(round(row), round(column), '*')
    await sleep()
    canvas.addstr(round(row), round(column), 'O')
    await sleep()
    canvas.addstr(round(row), round(column), ' ')

    row += rows_speed
    column += columns_speed

    symbol = '-' if columns_speed else '|'
    rows, columns = canvas.getmaxyx()
    max_row, max_column = rows - BORDER_LENGTH, columns - BORDER_LENGTH

    curses.beep()

    while 0 < row < max_row and 0 < column < max_column:
        for obstacle in obstacles:
            if obstacle.has_collision(row, column):
                obstacles_in_last_collisions.append(obstacle)
                return
        canvas.addstr(round(row), round(column), symbol)
        await sleep()
        canvas.addstr(round(row), round(column), ' ')
        row += rows_speed
        column += columns_speed


async def run_spaceship(canvas, start_row, start_column):
    """Display animation of a spaceship."""
    spaceship_frame_files = [
        os.path.join(SPACESHIP_FRAMES_FOLDER, file) for file in os.listdir(SPACESHIP_FRAMES_FOLDER)
    ]
    spaceship_frames = read_frames(spaceship_frame_files)

    tics_between_animations = 2

    max_rows, max_columns = (max_coordinate - BORDER_LENGTH for max_coordinate in canvas.getmaxyx())
    min_rows = min_columns = BORDER_LENGTH
    row, column = start_row, start_column
    row_speed = column_speed = 0

    spaceship_animations_cycle = itertools.chain.from_iterable(
        [[frame]*tics_between_animations for frame in spaceship_frames]
    )

    for spaceship_frame in itertools.cycle(spaceship_animations_cycle):
        rows_direction, columns_direction, fire_button_pressed = read_controls(canvas)
        row_speed, column_speed = update_speed(
            row_speed, column_speed, rows_direction, columns_direction
        )
        row = row + row_speed
        column = column + column_speed
        spaceship_size_rows, spaceship_size_columns = get_frame_size(spaceship_frame)
        row = max(row, min_rows)
        row = min(row, max_rows - spaceship_size_rows)
        column = max(column, min_columns)
        column = min(column, max_columns - spaceship_size_columns)

        if fire_button_pressed and year >= GUN_AVAILABLE_YEAR:
            spaceship_center_column = column + spaceship_size_columns // 2
            coroutines.append(
                draw_fire(canvas, start_row=row, start_column=spaceship_center_column)
            )
        draw_frame(canvas, row, column, spaceship_frame)
        await sleep()
        draw_frame(canvas, row, column, spaceship_frame, negative=True)

        for obstacle in obstacles:
            if obstacle.has_collision(row, column, spaceship_size_rows, spaceship_size_columns):
                obstacles_in_last_collisions.append(obstacle)
                coroutines.append(show_gameover(canvas))
                return


async def show_gameover(canvas):
    """Show "Game Over" text in the center of the screen."""
    gameover_frame = read_frames([GAME_OVER_FRAME_FILE])[0]
    gameover_frame_size_rows, gameover_frame_size_columns = get_frame_size(gameover_frame)
    central_row, central_column = (max_coordinate // 2 for max_coordinate in canvas.getmaxyx())

    row = central_row - gameover_frame_size_rows // 2
    column = central_column - gameover_frame_size_columns // 2

    while True:
        draw_frame(canvas, row, column, gameover_frame)
        await sleep()


def main(canvas):
    canvas.border()
    canvas.nodelay(True)
    curses.curs_set(0)

    global coroutines
    global obstacles

    create_stars(canvas, count=100)

    central_row, central_column = (max_coordinate//2 for max_coordinate in canvas.getmaxyx())
    coroutines.append(
        run_spaceship(
            canvas=canvas,
            start_row=central_row,
            start_column=central_column
        )
    )

    coroutines.append(fill_orbit_with_garbage(canvas))
    coroutines.append(handle_year(TICS_PER_YEAR))
    coroutines.append(show_caption(canvas))
    if SHOW_OBSTACLES:
        coroutines.append((show_obstacles(canvas, obstacles)))

    while True:
        for coroutine in coroutines.copy():
            try:
                coroutine.send(None)
            except StopIteration:
                coroutines.remove(coroutine)
        canvas.refresh()
        time.sleep(TIC_TIMEOUT)


if __name__ == '__main__':
    curses.update_lines_cols()
    curses.wrapper(main)
