"""ActionPlugin entry point — wires up wx file dialog, copy, transform, save."""

import os
import traceback

import pcbnew

try:
    import wx
except ImportError:
    wx = None

from .transform import build_faceplate


class EurorackFaceplatePlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Generate Eurorack Faceplate"
        self.category = "Modify PCB"
        self.description = (
            "Generate a Eurorack faceplate PCB from the current PCB. "
            "Footprints with a 'Faceplate' field are replaced with their "
            "panel-hole equivalents; everything else is stripped."
        )
        self.show_toolbar_button = True
        icon = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon):
            self.icon_file_name = icon

    def Run(self):
        try:
            self._run()
        except Exception as exc:
            self._error(
                f"Faceplate generation failed:\n\n{exc}\n\n"
                f"{traceback.format_exc()}"
            )

    def _run(self):
        board = pcbnew.GetBoard()
        src_path = board.GetFileName()
        if not src_path or not os.path.isfile(src_path):
            self._error("Save the PCB to disk before running the faceplate generator.")
            return

        dest_path = self._ask_dest_path(src_path)
        if not dest_path:
            return

        # Save the live board *as-is* to the destination path. This captures any
        # unsaved edits the user has made in pcbnew (e.g. fields just added) and
        # never overwrites the source file. Then we load that fresh file and
        # transform it — the live board is never mutated.
        pcbnew.SaveBoard(dest_path, board)
        dest_board = pcbnew.LoadBoard(dest_path)
        hp, panel_count, diag = build_faceplate(dest_board)
        pcbnew.SaveBoard(dest_path, dest_board)

        msg = (
            f"Faceplate ({hp} HP, {panel_count} panel parts placed) saved to:\n"
            f"{dest_path}\n\nOpen it from File → Open to review."
        )
        if panel_count == 0:
            msg += (
                "\n\nNo footprints had a 'Faceplate' field set. "
                "Field name must be exactly 'Faceplate' (case sensitive) "
                "and value 'Faceplate:<FootprintName>'.\n\n"
                "Footprints scanned:\n" + (diag or "  <none>")
            )
        self._info(msg)

    def _ask_dest_path(self, src_path):
        default_name = os.path.basename(src_path).replace(
            ".kicad_pcb", "_faceplate.kicad_pcb"
        )
        if wx is None:
            return os.path.join(os.path.dirname(src_path), default_name)

        with wx.FileDialog(
            None,
            message="Save Eurorack faceplate as",
            defaultDir=os.path.dirname(src_path),
            defaultFile=default_name,
            wildcard="KiCad PCB (*.kicad_pcb)|*.kicad_pcb",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return None
            return dlg.GetPath()

    def _info(self, message):
        if wx is not None:
            wx.MessageBox(message, "Eurorack Faceplate", wx.OK | wx.ICON_INFORMATION)
        else:
            print(message)

    def _error(self, message):
        if wx is not None:
            wx.MessageBox(
                message, "Eurorack Faceplate — Error", wx.OK | wx.ICON_ERROR
            )
        else:
            print(f"ERROR: {message}")
