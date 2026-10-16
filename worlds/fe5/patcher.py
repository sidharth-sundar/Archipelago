"""Thin CLI/GUI entry point; also builds as a standalone Windows EXE."""
import argparse
import sys
import zipfile

try:
    from .patchcore import patch_file
except ImportError:  # PyInstaller / direct standalone entry point
    from patchcore import patch_file


def main():
    parser = argparse.ArgumentParser(description="Apply a Thracia AP seed to unmodified Lil' Manster 1.08")
    parser.add_argument("--base")
    parser.add_argument("--patch")
    parser.add_argument("--output")
    args = parser.parse_args()
    gui = not any((args.base, args.patch, args.output))
    if gui:
        import tkinter as tk
        from tkinter import filedialog, messagebox
        root = tk.Tk()
        root.withdraw()
        args.base = filedialog.askopenfilename(title="Select unmodified Lil' Manster 1.08", filetypes=[("SNES ROM", "*.sfc")])
        if not args.base:
            return 0
        args.patch = filedialog.askopenfilename(title="Select generated Thracia AP seed", filetypes=[("Thracia AP patch", "*.apfe5")])
        if not args.patch:
            return 0
        args.output = filedialog.asksaveasfilename(title="Save patched ROM", defaultextension=".sfc", filetypes=[("SNES ROM", "*.sfc")])
        if not args.output:
            return 0
    elif not all((args.base, args.patch, args.output)):
        parser.error("Supply --base, --patch and --output together, or no arguments for file selection")
    try:
        output = patch_file(args.base, args.patch, args.output)
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as exc:
        if gui:
            messagebox.showerror("Thracia AP patch failed", str(exc))
        else:
            print(f"Patch failed: {exc}", file=sys.stderr)
        return 1
    if gui:
        messagebox.showinfo("Thracia AP patch complete", f"Created {output}")
    else:
        print(f"Created {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
