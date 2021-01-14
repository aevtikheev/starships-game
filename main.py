import asyncio
import curses
import time
import random
import os
import itertools

from tools import get_frame_size, draw_frame, read_frames, read_controls
from physics import update_speed
from obstacles import Obstacle, has_collision, show_obstacles


TIC_TIMEOUT = 0.1

FRAMES_FOLDER = 'frames'
SPACESHIP_FRAMES_FOLDER = os.path.join(FRAMES_FOLDER, 'spaceship')
GARBAGE_FRAMES_FOLDER = os.path.join(FRAMES_FOLDER, 'garbage')

BORDER_LENGTH = 1


coroutines = []
obstacles = []
obstacles_in_last_collisions = []


async def sleep(tics=1):
    for _ in range(tics):
        await asyncio.sleep(0)


async def draw_star(canvas, row, column, symbol='*', offset_tics=0):
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
    star_size = 1
    max_rows, max_columns = (max_coordinate - star_size - BORDER_LENGTH for max_coordinate in canvas.getmaxyx())
    min_rows = min_columns = BORDER_LENGTH

    global coroutines
    for _ in range(count):
        row = random.randint(min_rows, max_rows)
        column = random.randint(min_columns, max_columns)
        symbol = random.choice('+*.:')
        offset_blink = random.randint(1, 20)
        coroutines.append(draw_star(canvas, row, column, symbol, offset_blink))


async def fill_orbit_with_garbage(canvas, delay_tics):
    garbage_frame_files = [
        os.path.join(GARBAGE_FRAMES_FOLDER, file) for file in os.listdir(GARBAGE_FRAMES_FOLDER)
    ]
    garbage_frames = read_frames(garbage_frame_files)

    global coroutines
    while True:
        coroutines.append(
            fly_garbage(
                canvas=canvas,
                column=random.randint(0, canvas.getmaxyx()[1]),
                garbage_frame=random.choice(garbage_frames)
            )
        )
        await sleep(delay_tics)


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


async def draw_spaceship(canvas, start_row, start_column):
    """Display animation of a spaceship."""
    spaceship_frame_files = [
        os.path.join(SPACESHIP_FRAMES_FOLDER, file) for file in os.listdir(SPACESHIP_FRAMES_FOLDER)
    ]
    spaceship_frames = read_frames(spaceship_frame_files)

    tics_between_animations = 2

    max_rows, max_columns = (x - BORDER_LENGTH for x in canvas.getmaxyx())
    min_rows = min_columns = BORDER_LENGTH
    row, column = start_row, start_column
    row_speed = column_speed = 0

    spaceship_animations_cycle = itertools.chain.from_iterable(
        [[frame]*tics_between_animations for frame in spaceship_frames]
    )

    for spaceship_frame in itertools.cycle(spaceship_animations_cycle):
        rows_direction, columns_direction, fire = read_controls(canvas)
        row_speed, column_speed = update_speed(row_speed, column_speed, rows_direction, columns_direction)
        row = row + row_speed
        column = column + column_speed
        spaceship_size_rows, spaceship_size_columns = get_frame_size(spaceship_frame)
        row = max(row, min_rows)
        row = min(row, max_rows - spaceship_size_rows)
        column = max(column, min_columns)
        column = min(column, max_columns - spaceship_size_columns)

        if fire:
            spaceship_center_column = column + spaceship_size_columns // 2
            coroutines.append(
                draw_fire(canvas, start_row=row, start_column=spaceship_center_column)
            )
        draw_frame(canvas, row, column, spaceship_frame)
        await sleep()
        draw_frame(canvas, row, column, spaceship_frame, negative=True)


async def fly_garbage(canvas, column, garbage_frame, speed=0.5):
    """Animate garbage, flying from top to bottom. Сolumn position will stay same, as specified on start."""
    rows_number, columns_number = canvas.getmaxyx()
    column = max(column, 0)
    column = min(column, columns_number - 1)
    row = 0

    obstacle = Obstacle(row, column, *get_frame_size(garbage_frame))
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
                return
    finally:
        obstacles.remove(obstacle)


def main(canvas):
    canvas.border()
    canvas.nodelay(True)
    curses.curs_set(0)

    global coroutines
    global obstacles

    create_stars(canvas, count=100)

    central_row, central_column = (x//2 for x in canvas.getmaxyx())
    coroutines.append(
        draw_spaceship(
            canvas=canvas,
            start_row=central_row,
            start_column=central_column
        )
    )

    coroutines.append(fill_orbit_with_garbage(canvas, delay_tics=20))
    coroutines.append((show_obstacles(canvas, obstacles)))

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
