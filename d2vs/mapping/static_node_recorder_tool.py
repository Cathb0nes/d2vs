import json

import keyboard

from time import sleep

import numpy as np
from cv2 import cv2

from d2vs.mapping.capture2 import map_diff, map_capture, map_merge_features
from d2vs.mapping.padtransf import ImageMergeException
from d2vs.mapping.pathing import Node
from d2vs.utils import NpEncoder, windows_say


class AutoRecorder:
    def __init__(self, area_name, load_existing=False, prev_node=None):
        """

        :param area_name:
        :param load_existing:
        :param prev_node: (x, y) coords of the node to start drawing from, empty to make a new (10_000, 10_000) start node
        """
        # if start_node or prev_node:
        #     assert start_node and prev_node, "If you supply a start_node/prev_node/nodes, you must also supply the others"

        self.area_name = area_name

        self.load_existing = load_existing

        # Node the level starts from/is relative to .. the (10_000, 10_000) coordinate Node
        self.start_node = None

        # We make map in record_first_node, or load existing map
        self.map = None

        # Holds our nodes, keys are tuple of (x, y) value is Node
        self.nodes = {}
        if load_existing:
            try:
                node_data = json.loads(open(self._get_area_level_json_path(), "r").read())
            except FileNotFoundError:
                node_data = {}

            # Loop over data once and make initial set of nodes
            for n in node_data:
                # pop data not used in class creation
                n_copy = n.copy()
                n_copy.pop("connections")
                n_copy.pop("interactables")
                node = Node(**n_copy)
                self.nodes[(node.x, node.y)] = node

                if node.is_start:
                    assert self.start_node is None, "We found multiple start nodes?! tried setting it twice"
                    self.start_node = node

            # Loop over data again and make connections
            for n in node_data:
                for c_x, c_y in n["connections"]:
                    self.nodes[(n["x"], n["y"])].add_connection(self.nodes[(c_x, c_y)])

            try:
                self.map = cv2.imread(self._get_area_level_png_path())
            except FileNotFoundError:
                self.map = None


        # Points to last created node
        if prev_node:
            self.prev_node = self.nodes[tuple(prev_node)]
        else:
            self.prev_node = None

        # Location of red dot (start) on map
        self.last_base_x, self.lase_base_y = None, None

    def _get_area_level_png_path(self):
        return f"areas/static_data/{self.area_name}.png"

    def _get_area_level_json_path(self):
        return f"areas/static_data/{self.area_name}.json"

    def record_first_node(self):
        self.map = map_diff(*map_capture(), is_start=True)

        # Debug: show map
        # cv2.imshow("map map", self.map)
        # cv2.waitKey(0)

        self.start_node = Node(
            10_000,
            10_000,
            is_start=True,
        )
        self.nodes[(self.start_node.x, self.start_node.y)] = self.start_node
        self.last_base_x, self.lase_base_y = (0, 0)
        self.prev_node = self.start_node

    def record_new_node(self):
        # Maybe we're trying to record the first node? do that instead!
        if isinstance(self.map, type(None)) and not self.load_existing:
            # no map supplied, we must have skipped record_first_node?
            # self.map = map_diff(*map_capture(), is_start=True)
            # self.prev_node =
            self.record_first_node()
            return

        assert not isinstance(self.map, type(None)), "You have to have a base static map to work from, by calling record_first_node or saving static_data/area_name.png"

        diff = map_diff(*map_capture(), threshold=.15)

        # Debug: show diff
        # cv2.imshow("map diff", diff)
        # cv2.waitKey(0)

        try:
            new_map, x, y, self.last_base_x, self.lase_base_y = map_merge_features(self.map, diff)

            if not self.load_existing:
                self.map = new_map

            # TODO: sanity check, is this node too close to a previous one? may min distance is like 20 pixels?

            new_node = Node(x, y)

            self.nodes[(new_node.x, new_node.y)] = new_node

            # TODO: also connect all nodes within ??? range?
            self.prev_node.add_connection(new_node)  # connect previous to new
            self.prev_node = new_node  # new is now the old!

            print(x, y)
        except ImageMergeException as e:
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print(e)
            windows_say("Failed")

    def finish(self):
        # node = self.start_node
        # while True:
        #     print(node)

        # print(self.start_node)





        # Dump the static map, TODO: make this optional? don't need to do this after a while?
        if not self.load_existing:
            cv2.imwrite(self._get_area_level_png_path(), self.map)

        # Dump the node data to json
        self.dump_nodes()

        self.view_map()

    def dump_nodes(self):
        node_dict_data = []
        for node in self.nodes.values():
            node_data = node.to_dict()
            print(f"Adding node_data: {node_data}")
            node_dict_data.append(node_data)

        with open(self._get_area_level_json_path(), "w") as f:
            f.write(json.dumps(node_dict_data, cls=NpEncoder, indent=4))

    def draw_map_with_nodes(self):
        map_copy = self.map.copy()

        # lighten map color so easier to see debug shit
        map_copy[np.where((map_copy == [255, 255, 255]).all(axis=2))] = [0x70, 0x70, 0x70]

        # Delete any old green markers for "current location"
        map_copy[np.all(map_copy == [0, 255, 0], axis=-1)] = [0, 0, 0]

        for node in self.nodes.values():
            # Go back from 10_000, 10_000 based coordinate system to 0, 0 based for drawing this on our diff
            x = node.x + self.last_base_x - 10_000
            y = node.y + self.lase_base_y - 10_000
            print(f"Drawing node from ({node.x}, {node.y}) to ({x}, {y})")
            FONT_HERSHEY_COMPLEX_SMALL = 5
            cv2.putText(map_copy, f"{node.x}, {node.y}", (x - 20, y - 10), FONT_HERSHEY_COMPLEX_SMALL, .66,
                        (0x00, 0xff, 0x00), 1)

            if node.is_start:
                color = (0x00, 0x00, 0xff)
            else:
                color = (0x00, 0xff, 0x00)

            # NOTE: this is 3px radius, red circle marking start location is only 2px .. shouldn't matter much ..
            cv2.circle(map_copy, (x, y), 3, color, -1)

            for conn in node.get_connections():
                conn_new_x = conn.x + self.last_base_x - 10_000
                conn_new_y = conn.y + self.lase_base_y - 10_000

                cv2.line(map_copy, (x, y), (conn_new_x, conn_new_y), (0x00, 0xff, 0x00))
        return map_copy

    def view_map(self):
        map = self.draw_map_with_nodes()
        cv2.imshow("map with nodes", map)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":

    # TODO: Make the first capture not automatic? Either auto-first node or you can select a node to extend

    import tkinter as tk
    from tkinter import messagebox, simpledialog, Entry, END


    # Have to do this to start Tk
    tk_root = tk.Tk()
    tk_root.overrideredirect(1)
    tk_root.withdraw()

    kwargs = {
        # "load_existing": messagebox.askokcancel("Overwrite", "Load existing area? (if no, you may overwrite something!)"),
        # "area_name": simpledialog.askstring(title="Area name?", prompt="What's the AreaLevel you're working on?", initialvalue="Harrogath")
        "load_existing": False,

        # "load_existing": True,
        "area_name": "Harrogath",
        # "prev_node": (10_000, 10_000),
    }

    # if kwargs["load_existing"]:
    #     prev_node_coords = simpledialog.askstring(
    #         title="Area name?",
    #         prompt="Enter 'x, y' for the node would you like to add to. Ie '10_000, 10_000' to start from the original "
    #                "start (underscores deleted before processing)",
    #         initialvalue="10_000,10_000"
    #     )
    #     prev_x, prev_y = prev_node_coords.replace("_", "").replace(" ", "").split(",")  # tuple (x, y)
    #     kwargs["prev_node"] = (int(prev_x), int(prev_y))

    recorder = AutoRecorder(**kwargs)

    keyboard.add_hotkey("scroll lock", recorder.record_new_node)
    keyboard.add_hotkey("f11", recorder.view_map)
    keyboard.add_hotkey("pause break", recorder.finish)

    # TODO: Select some particular node to start connecting from?

    # wait forever
    while True:
        sleep(.1)
