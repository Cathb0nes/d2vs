import os
from datetime import datetime

import keyboard
import numpy as np
import pyautogui

from time import sleep, time
from threading import Thread

from d2vs.exceptions import ChickenException, CanNoLongerBotException
from d2vs.helpers import click, shift_attack, coord_translation
from d2vs.modules import Town, Chicken, PickIt
from d2vs.ocr import OCR
from d2vs.pickit import is_pickable, pick_area
from d2vs.thread_hacks import ctype_async_raise
from d2vs.window import Window

# DO_MONSTER_SCAN = False
# DO_ITEM_SCAN = False
from state_checks import is_corpse_on_ground, is_at_character_select_screen, is_in_queue, is_mercenary_alive, is_in_game


#
#
# def ocr_loop():
#     # ocr = OCR()
#
#     potential_immunities = ["poison", "lightning", "cold", "fire"]
#
#     while True:
#         if DO_MONSTER_SCAN:
#             pindle_immunities = []
#             bounds = ocr.read(773, 5, 1772, 200)
#
#             # is this a pindle mouse over?
#             all_text = " ".join([text.lower() for (_, text, _) in bounds])
#
#             if "pindle" in all_text:
#                 for immunity in potential_immunities:
#                     if f"immune to {immunity}" in all_text:
#                         pindle_immunities.append(immunity)
#
#                 print(f"Pindle immunities seen: {pindle_immunities}")
#
#         if DO_ITEM_SCAN:
#             scan_area(ocr)
#
#         sleep(.01)  # don't use 100% cpu
#
# Thread(target=ocr_loop).start()



# sleep(2)
# pick_area(ocr, 1150, 150, 2300, 750)
#
#
#
# sleep(500)



class Bot:

    def __init__(self):
        OCR()  # OCR is singleton, this initializes it
        self.window = Window()

        self.modules = {
            "Town": Town(),
            "Chicken": Chicken(),
            "PickIt": PickIt(),
        }

        self.screen_scan_thread = None
        self.game_thread = None

        # Setup Hotkeys for controlling bot..
        # keyboard.add_hotkey('pause', lambda: exit(1))  # .... does not work ....

    def _screen_scan_loop(self):
        while True:
            if pyautogui.getActiveWindowTitle() != "Diablo II: Resurrected":
                sleep(.1)
                continue

            try:
                screen_data = np.array(self.window.screen)

                # This should be just about the only place we do that. Capturing the screen is relatively expensive.
                OCR().set_screen_data(screen_data)

                for name, module in self.modules.items():
                    module.on_screen_capture(screen_data)
                sleep(.01)
            except ChickenException:
                # Re-raise this chicken event in our game bot thread
                ctype_async_raise(self.game_thread.ident, ChickenException)

    def _game_loop_wrapper(self):
        """This wrapper is for catching chicken events and such..."""
        while True:
            try:
                self._game_loop()
            except ChickenException:
                print(f"Chickening @ {datetime.now():%m/%d/%Y %I:%M%p}!!!")
                pyautogui.press('esc')
                click(1275, 633, delay=.25)
            except CanNoLongerBotException as e:
                print(f"Can't bot any longer: {e}")

    def _game_loop(self):
        # make sure game started
        win = pyautogui.getWindowsWithTitle("Diablo II: Resurrected")

        if win and any(w.title == "Diablo II: Resurrected" for w in win):  # make sure it's the exact title and not some youtube video!
            # Get first window matching exact title..
            win = [w for w in win if w.title == "Diablo II: Resurrected"]

            win[0].activate()

            # Let screen scan fill OCR with data before we start
            sleep(1)
        else:
            # Game wasn't even open yet..
            print("Game not even started yet, starting..")
            os.startfile("C:\Program Files (x86)\Diablo II Resurrected\D2R.exe")
            sleep(10)
            pyautogui.press('space')  # intro video..
            sleep(3)
            pyautogui.press('space')  # another thing ??
            sleep(10)
            pyautogui.press('space')  # press any key to continue bullshit ...
            sleep(3)

        # In queue?
        queue_check_count = 0
        while is_in_queue():
            if queue_check_count == 0:
                print("Waiting in queue!!! waiting 10 seconds to check again..")
            sleep(10)
            queue_check_count += 1

        # Back at char selection? OR maybe we're in game?
        if not is_in_game():
            char_screen_retries = 1
            while not is_at_character_select_screen() and char_screen_retries < 3:
                sleep(2 * char_screen_retries)
                char_screen_retries += 1

            if char_screen_retries >= 3:
                # TODO: Restart game here if we've tried this a few times???
                print("We're not at online char select screen yet, clicking 'Online' to try and get back..")
                click(2185, 71, delay=1)
                return

            # Start game...
            click(1059, 1285)
            click(1275, 782, delay=.1)
        else:
            # Already in game??
            # TODO: Exit game... no idea what state we're in. Go back to start ???
            pass

        # Wait until we're for sure in game..
        is_in_game_timeout_seconds = 30
        is_in_game_current_time = time()
        while not is_in_game() and time() - is_in_game_current_time < is_in_game_timeout_seconds:
            sleep(1)

        if time() - is_in_game_current_time >= is_in_game_timeout_seconds:
            # no idea what state we're in. Go back to start ???
            print("we timed out ???")
            return

        # print("We're in game.")

        # TODO: Confirm we eventually see loading ...

        # Game started ...
        for name, module in self.modules.items():
            module.on_game_start()
        # self.modules["Town"]

        # Did we die?
        if is_corpse_on_ground():
            print("Corpse found! Picking up...")
            click(1276, 672)

        # Are we in act 4 or act 5? did we fuck up?
        # TODO: CHECK THIS!

        # Go near WP and prepare for merc check...
        click(765, 1200)
        click(800, 1145, delay=1.45)

        # Is merc alive?
        if is_mercenary_alive():
            # go straight to red portal
            # print("ahoy merc nice to see ya")
            click(999, 1286, delay=1.55)  # this goes past WP next to lil rock wall (2 clicks close together works nice for some reason ..)
            click(999, 1286, delay=.05)
            click(1131, 1269, delay=1.45)
        else:
            # go to Act 4, revive merc, come back, resume path to go to red portal
            print("merc DEAD!")

            click(1155, 916, delay=1.5)  # click wp
            click(659, 295, delay=1.0)   # click act 4
            click(319, 358, delay=1.5)   # click Pandamonium Fortress
            click(315, 10, delay=8.5)    # click Tyrael

            # Search for "Resurrect: " text and click the center of it
            x1, y1 = coord_translation(512, 16)
            x2, y2 = coord_translation(1697, 699)
            resurrect_readings = OCR().read(x1, y1, x2, y2, delay=2.5, coords_have_been_translated=True)
            print("resurrect_readings results:")
            print(resurrect_readings)
            for (top_left, top_right, bottom_right, bottom_left), text, _ in resurrect_readings:
                if "resurrect" in text.lower():
                    center_y = int(y1 + top_left[1] + ((bottom_right[1] - top_left[1]) / 2))
                    center_x = int(x1 + top_left[0] + 6)

                    # click resurrect
                    click(center_x, center_y)

                    # ..did we not have enough gold? check if merc alive
                    sleep(1.5)
                    if not is_mercenary_alive():
                        raise CanNoLongerBotException("Can no longer bot. no mercenary :( not enough gold to revive.")
                    break

            click(2125, 1059, delay=1.0)  # click wp
            click(774, 292, delay=2.5)    # click act 5
            click(322, 350, delay=1.0)    # click harrogath
            click(1135, 1014, delay=8.5)  # click next to rock wall and continue normal path

        click(641, 883, delay=1.3)
        pyautogui.press('f7')  # telekenisis
        click(350, 475, delay=1.4, button="right")
        click(350, 400, delay=.5, button="right")  # sometimes first one doesnt work ... click a little up
        click(435, 325, delay=.5, button="right")  # sometimes first one doesnt work ... click a lot up and to the right

        # TP to pindle
        sleep(1)
        pyautogui.press('f5')  # teleport

        click(1400, 700, delay=1.25)  # take a quick step forward before TPing

        click(2535, 25, delay=.45, button="right")
        click(2535, 25, delay=.45, button="right")

        pyautogui.press('f2')  # set blizzard up
        click(1557, 352, delay=.45, button="right")  # blizz

        # Glacier opener
        shift_attack(1557, 352)

        # Final attack combo
        for _ in range(2):
            shift_attack(1557, 352, duration=1.75)  # glaciers
            click(1557, 352, delay=.5, button="right")  # blizz

        # wait for merc to maybe kill cold immune guy?
        sleep(1.5)

        # click(1815, 315, delay=1.25, button="right")
        # click(1815, 315, delay=.45, button="right")
        # click(1815, 315, delay=.45, button="right")
        # click(1815, 315, delay=.45, button="right")
        #
        # # Attack sequence ----------------------------------------------------
        # # Glacier opener
        # shift_attack(1700, 500)
        #
        # # Blizz then move forward
        # pyautogui.press('f2')  # blizzard
        # click(1925, 355, delay=.5, button="right")
        # click(1425, 650, delay=1.15)
        # sleep(.5)
        #
        # # Final attack combo
        # for _ in range(1):
        #     shift_attack(1700, 450, duration=1.5)  # glaciers
        #     click(1775, 400, delay=.375, button="right")  # blizz

        # Read under cursor, cold immune?
        # todo..

        # Check items?
        # pyautogui.press('f5')  # teleport
        # click(1775, 400, delay=.5, button="right")
        pick_area(700, 1, 2599, 750)

        # leave game...
        pyautogui.press('esc')
        click(1275, 633, delay=.5)

        # wait for next!
        sleep(25)

        # loop:
        #   - start game if not running, click to char screen
        #   - start hell game
        #   - do town management
        #   - do pindle, would be nice to know if he's cold immune
        #   - scan for items
        #   - leave

    def run(self):
        # daemon=True here so when we close the app this thread closes cleanly, doesn't seem to otherwise..
        # may not be helpful..
        self.screen_scan_thread = Thread(target=self._screen_scan_loop, daemon=True)
        self.screen_scan_thread.start()

        self.game_thread = Thread(target=self._game_loop_wrapper, daemon=True)
        self.game_thread.start()

        while True:
            # go forever!
            sleep(1)



bot = Bot()
bot.run()












exit()
















# print(is_corpse_on_ground())
#
#
#
# sleep(500)









# Wait for game to maximize...
sleep(2)

while True:
    if pyautogui.getActiveWindowTitle() != "Diablo II: Resurrected":
        print("Diablo 2 not active any more, something bad happened!")
        break

    # Start hell game..
    click(1059, 1285)
    click(1275, 782, delay=.25)

    # Wait for game to load..
    # TOOD: Actually wait, smartly!
    sleep(13)

    # TODO: do we need to pickup our body?



    # TODO: do we need to revive merc? (go to act 4 and do it, then come back)

    # TODO: detect: are we in act 4 or 5?

    # TODO: go to red portal, however we have to get there...


    # Go from a5 start to red portal
    click(765, 1200)
    click(800, 1145, delay=1.45)
    click(999, 1286, delay=1.55)
    click(999, 1286, delay=.05)
    click(1131, 1269, delay=1.45)



    click(641, 883, delay=1.3)
    pyautogui.press('f7')  # telekenisis
    click(350, 475, delay=1.4, button="right")
    click(350, 400, delay=.5, button="right")  # sometimes first one doesnt work ... click a little up
    click(420, 350, delay=.5, button="right")  # sometimes first one doesnt work ... click a lot up and to the right

    # TP to pindle
    sleep(1)
    pyautogui.press('f5')  # teleport

    click(1400, 700, delay=1.25)  # take a quick step forward before TPing

    click(2535, 25, delay=.45, button="right")
    click(2535, 25, delay=.45, button="right")

    pyautogui.press('f2')  # set blizzard up
    click(1557, 352, delay=.45, button="right")  # blizz

    # Glacier opener
    shift_attack(1557, 352)

    # Final attack combo
    for _ in range(2):
        shift_attack(1557, 352, duration=1.75)  # glaciers
        click(1557, 352, delay=.5, button="right")  # blizz

    # wait for merc to maybe kill cold immune guy?
    sleep(1.5)



    # click(1815, 315, delay=1.25, button="right")
    # click(1815, 315, delay=.45, button="right")
    # click(1815, 315, delay=.45, button="right")
    # click(1815, 315, delay=.45, button="right")
    #
    # # Attack sequence ----------------------------------------------------
    # # Glacier opener
    # shift_attack(1700, 500)
    #
    # # Blizz then move forward
    # pyautogui.press('f2')  # blizzard
    # click(1925, 355, delay=.5, button="right")
    # click(1425, 650, delay=1.15)
    # sleep(.5)
    #
    # # Final attack combo
    # for _ in range(1):
    #     shift_attack(1700, 450, duration=1.5)  # glaciers
    #     click(1775, 400, delay=.375, button="right")  # blizz




    # Read under cursor, cold immune?
    # todo..

    # Check items?
    # pyautogui.press('f5')  # teleport
    # click(1775, 400, delay=.5, button="right")
    pick_area(ocr, 700, 1, 2599, 750)

    # leave game...
    pyautogui.press('esc')
    click(1275, 633, delay=.5)

    # wait for next!
    sleep(25)