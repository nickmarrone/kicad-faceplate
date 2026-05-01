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

        if not self._confirm_saved():
            return

        dest_path = self._ask_dest_path(src_path)
        if not dest_path:
            return

        if os.path.realpath(dest_path) == os.path.realpath(src_path):
            self._error(
                "Destination is the same as the source PCB.\n"
                "Pick a different filename — the plugin refuses to overwrite the original."
            )
            return

        # Filesystem-level copy: the source file is read once and never written.
        # This is the only safe way to guarantee the original PCB cannot be
        # touched, even if a downstream KiCad call has a side-effect on the
        # board's filename. We never call SaveBoard with the live `board`.
        shutil.copyfile(src_path, dest_path)

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

    def _confirm_saved(self):
        """Remind the user to save first. We read the PCB from disk, so any
        unsaved in-editor edits won't be picked up — and we want to be loud
        about it after a previous version of this plugin lost data."""
        if wx is None:
            return True
        res = wx.MessageBox(
            "The faceplate generator reads the PCB from disk.\n\n"
            "Make sure you have saved your PCB (File → Save / Ctrl+S) "
            "before continuing — any unsaved edits will be ignored.\n\n"
            "The original PCB will not be modified.\n\n"
            "Continue?",
            "Eurorack Faceplate",
            style=wx.YES_NO | wx.ICON_INFORMATION | wx.YES_DEFAULT,
        )
        return res == wx.YES

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
