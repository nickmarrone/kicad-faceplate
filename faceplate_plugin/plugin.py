"""ActionPlugin entry point — wires up wx file dialog, copy, transform, save."""

import os
import shutil
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

        shutil.copy(src_path, dest_path)
        dest_board = pcbnew.LoadBoard(dest_path)
        hp = build_faceplate(dest_board)
        pcbnew.SaveBoard(dest_path, dest_board)

        self._info(
            f"Faceplate ({hp} HP) saved to:\n{dest_path}\n\n"
            f"Open it from File → Open to review."
        )

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
