#!/usr/bin/env python3
"""
  HEIC -> JPG  |  Converter CLI  |  v4.0
"""

import os
import sys
import time
import random
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from heic_engine import (
    find_heic_files, get_output_path, convert_file, execute_convert,
    save_history, load_history, undo_last, check_heif_support, HAS_HEIF,
)

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# -- Rich imports -------------------------------------------------------------

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        Progress, BarColumn, TextColumn, TimeRemainingColumn,
        SpinnerColumn, TaskProgressColumn,
    )
    from rich.table import Table
    from rich.prompt import Prompt, Confirm
    from rich.columns import Columns
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# -- Fallback -----------------------------------------------------------------

class FallbackConsole:
    def print(self, *args, **kwargs): print(*args)
    def input(self, prompt=""): return input(prompt)
    def status(self, *args, **kwargs): return self

if HAS_RICH:
    con = Console()
else:
    con = FallbackConsole()

# -- Stats --------------------------------------------------------------------

def show_stats(console, converted, skipped, errors, elapsed):
    if HAS_RICH:
        stats = Table.grid(padding=1)
        stats.add_column()
        stats.add_column(justify="right")
        stats.add_row("[bold green]OK Converted[/]", str(converted))
        stats.add_row("[dim]> Skipped[/]", str(skipped))
        stats.add_row("[bold red]! Errors[/]", str(errors))
        stats.add_row("[bold cyan]! Time[/]", f"{elapsed:.2f}s")
        stats.add_row("[bold yellow]* Speed[/]", f"{converted / max(elapsed, 0.01):.1f} files/s")
        con.print(Panel(stats, title="[bold]Mission Report[/]", border_style="bright_blue"))
    else:
        print("+--- Mission Report ---+")
        print(f"  OK Converted:  {converted}")
        print(f"  > Skipped:     {skipped}")
        print(f"  ! Errors:      {errors}")
        print(f"  ! Time:        {elapsed:.2f}s")
        print(f"  * Speed:       {converted / max(elapsed, 0.01):.1f} files/s")


def show_history_cli(console):
    history = load_history()
    if not history:
        return "No previous sessions found."
    if HAS_RICH:
        table = Table(title="[bold]Conversion History[/]", box=box.ROUNDED, border_style="cyan")
        table.add_column("Time", style="dim")
        table.add_column("Folder", style="cyan")
        table.add_column("Files", justify="right", style="green")
        for h in reversed(history[-10:]):
            convs = h.get("conversions", h.get("renames", []))
            table.add_row(h.get("timestamp", "?"), h.get("folder", "?"), str(len(convs)))
        return table
    else:
        lines = ["-- Conversion History --"]
        for h in reversed(history[-10:]):
            convs = h.get("conversions", h.get("renames", []))
            lines.append(f"  {h.get('timestamp','?'):20}  {len(convs)} files  {h.get('folder','?')}")
        return "\n".join(lines)


# -- Main ---------------------------------------------------------------------

def main():
    console = con

    # -- Check HEIF support ---------------------------------------------------
    ok, msg = check_heif_support()
    if not ok:
        console.print(f"[bold red]{msg}[/]")
        sys.exit(1)

    os.system("cls" if os.name == "nt" else "clear")

    if HAS_RICH:
        console.print(Panel(
            "[bold cyan]#[/] [bold white]HEIC[/] -> [bold yellow]JPG[/] [bold cyan]#[/]\n"
            "[dim]lossless conversion engine v4.0[/]",
            border_style="bright_cyan",
            box=box.HEAVY,
        ))
        console.print()
        with console.status("", spinner="dots12") as status:
            time.sleep(0.6)
            for _ in range(4):
                status.update(f"[dim]loading heif codec[/dim] {'#' * (random.randint(3,8))}")
                time.sleep(0.15)
    else:
        print("+----------------------------------+")
        print("|  # HEIC -> JPG #                 |")
        print("|  lossless conversion engine v4.0  |")
        print("+----------------------------------+")
        print()
        time.sleep(0.6)

    # -- Quality setting -------------------------------------------------------
    quality = 100
    quality_from_cli = False
    for i, arg in enumerate(sys.argv):
        if arg in ("-q", "--quality") and i + 1 < len(sys.argv):
            try:
                quality = int(sys.argv[i + 1])
                quality = max(1, min(100, quality))
                quality_from_cli = True
            except ValueError:
                pass

    if not (quality_from_cli or "-y" in sys.argv or "--yes" in sys.argv):
        if HAS_RICH:
            qual_str = Prompt.ask(
                "[bold cyan]Q[/] [white]JPEG quality[/] [dim](1-100, higher = better quality, larger file)[/]",
                default=str(quality),
            )
            try:
                quality = max(1, min(100, int(qual_str)))
            except ValueError:
                pass
        else:
            qual_str = input(f"JPEG quality (1-100) [{quality}]: ") or str(quality)
            try:
                quality = max(1, min(100, int(qual_str)))
            except ValueError:
                pass

    # -- Folder selection ----------------------------------------------------
    while True:
        default = str(Path.cwd())
        skip_input = False
        for arg in sys.argv[1:]:
            if not arg.startswith("-"):
                folder_str = arg
                skip_input = True
                break
        if not skip_input:
            if HAS_RICH:
                folder_str = Prompt.ask("[bold cyan][/] [white]Target folder[/]", default=default)
            else:
                folder_str = input(f"Target folder [{default}]: ") or default

        folder = Path(folder_str).expanduser().resolve()
        if not folder.exists():
            if HAS_RICH:
                console.print("[bold red][X][/] That dimension doesn't exist.", style="red")
            else:
                print("[X] That dimension doesn't exist.")
            continue
        if not folder.is_dir():
            if HAS_RICH:
                console.print("[bold red][X][/] That's not a folder.", style="red")
            else:
                print("[X] That's not a folder.")
            continue
        break

    # -- Scan -----------------------------------------------------------------
    if HAS_RICH:
        with console.status("[dim]scanning for .heic files...[/]", spinner="point"):
            heic_files = find_heic_files(folder)
    else:
        print("scanning for .heic files...")
        heic_files = find_heic_files(folder)

    if not heic_files:
        if HAS_RICH:
            console.print(Panel("[yellow][!][/] No .heic files found.", border_style="yellow", title="[bold]Void[/]"))
        else:
            print("[!] No .heic files found.")
        return

    # -- Preview -------------------------------------------------------------
    if HAS_RICH:
        table = Table(
            title=f"[bold cyan]*[/] [white]{len(heic_files)}[/] [dim]files @ Q{quality}[/]",
            box=box.SIMPLE, border_style="cyan", header_style="bold cyan",
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Source", style="white")
        table.add_column("->", style="dim", width=3)
        table.add_column("Output", style="green")
        table.add_column("Size", justify="right", style="dim")

        for i, f in enumerate(heic_files, 1):
            size = f.stat().st_size
            size_str = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024*1024):.1f} MB"
            new_name = get_output_path(f, dry_run=True).name
            table.add_row(str(i), f.name, "->", new_name, size_str)
        console.print()
        console.print(table)
        console.print()
        proceed = "-y" in sys.argv or "--yes" in sys.argv or Confirm.ask("[bold yellow]![/] Proceed with conversion?", default=True)
    else:
        print(f"\nFound {len(heic_files)} .heic file(s) @ Q{quality}:")
        for i, f in enumerate(heic_files, 1):
            print(f"  {i}. {f.name}  ->  {get_output_path(f, dry_run=True).name}")
        proceed = input("\nProceed? (Y/n): ").strip().lower() != 'n'

    if not proceed:
        console.print("[dim]aborted.[/]")
        return

    # -- Convert --------------------------------------------------------------
    converted = 0
    skipped = 0
    errors = 0
    conversions_log = []
    start_time = time.time()

    if HAS_RICH:
        progress = Progress(
            SpinnerColumn("dots12", style="cyan"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
            expand=True,
        )
        with progress:
            task = progress.add_task("[cyan]~ converting...", total=len(heic_files))
            for f in heic_files:
                target = get_output_path(f)
                if target.exists():
                    skipped += 1
                    progress.advance(task)
                    continue
                try:
                    result = convert_file(f, target, quality=quality)
                    conversions_log.append(result)
                    converted += 1
                    progress.update(task, description=f"[cyan]~[/] [dim]{f.name}[/] -> [green]{target.name}[/]")
                except Exception as e:
                    errors += 1
                    conversions_log.append({"source": str(f), "target": str(target), "error": str(e)})
                    progress.update(task, description=f"[bold red]![/] [dim]{f.name}[/] [red]error: {e}[/]")
                progress.advance(task)
    else:
        for i, f in enumerate(heic_files):
            target = get_output_path(f)
            if target.exists():
                skipped += 1
                print(f"  [{i+1}/{len(heic_files)}] > {f.name}  ->  already exists, skipped")
                continue
            try:
                result = convert_file(f, target, quality=quality)
                conversions_log.append(result)
                converted += 1
                print(f"  [{i+1}/{len(heic_files)}] OK {f.name}  ->  {target.name}  ({result['compression_ratio']}x)")
            except Exception as e:
                errors += 1
                conversions_log.append({"source": str(f), "target": str(target), "error": str(e)})
                print(f"  [{i+1}/{len(heic_files)}] ! {f.name}  ->  ERROR: {e}")

    elapsed = time.time() - start_time

    # -- Save history --------------------------------------------------------
    if conversions_log:
        save_history({
            "timestamp": datetime.now().isoformat(),
            "folder": str(folder),
            "conversions": conversions_log,
            "quality": quality,
            "elapsed": elapsed,
        })

    # -- Report --------------------------------------------------------------
    console.print()
    show_stats(console, converted, skipped, errors, elapsed)

    # -- Post-mission gadgets ------------------------------------------------
    if HAS_RICH:
        cols = Columns([
            Panel(f"[bold cyan]{len(heic_files)}[/]\n[dim]scanned", border_style="cyan"),
            Panel(f"[bold green]{converted}[/]\n[dim]converted", border_style="green"),
            Panel(f"[bold yellow]{skipped}[/]\n[dim]skipped", border_style="yellow"),
            Panel(f"[bold magenta]{elapsed:.2f}s[/]\n[dim]elapsed", border_style="magenta"),
        ])
        console.print(cols)
        console.print(Panel(
            "[dim]* originals preserved (never deleted)\n"
            "* use --undo to remove converted JPGs[/]",
            border_style="bright_black",
        ))
        console.print("\n[bold cyan]# conversion complete #[/]\n")
    else:
        print("# conversion complete #")

    # -- Interactive post-loop -----------------------------------------------
    if HAS_RICH and converted > 0 and "-y" not in sys.argv and "--yes" not in sys.argv:
        action = Prompt.ask(
            "[dim]>[/] [white]What next?[/]",
            choices=["quit", "history", "undo", "replay"],
            default="quit",
        )
        if action == "history":
            result = show_history_cli(console)
            console.print(result if isinstance(result, str) else result)
        elif action == "undo":
            ok, msg = undo_last()
            console.print(f"[bold green]OK[/] {msg}" if ok else f"[bold red][X][/] {msg}")
        elif action == "replay":
            console.print("[dim]restarting...[/]")
            main()
            return


# -- CLI entry ---------------------------------------------------------------

if __name__ == "__main__":
    if "--undo" in sys.argv:
        ok, msg = undo_last()
        if HAS_RICH:
            con.print(f"[bold green]OK[/] {msg}" if ok else f"[bold red][X][/] {msg}")
        else:
            print(msg if ok else f"[X] {msg}")
        sys.exit(0)

    if "--history" in sys.argv:
        result = show_history_cli(con)
        if HAS_RICH:
            con.print(result if isinstance(result, str) else result)
        else:
            print(result)
        sys.exit(0)

    if "--check" in sys.argv:
        ok, msg = check_heif_support()
        if HAS_RICH:
            con.print(f"[bold green]OK[/] {msg}" if ok else f"[bold red]FAIL[/] {msg}")
        else:
            print(msg if ok else f"FAIL: {msg}")
        sys.exit(0)

    try:
        main()
    except KeyboardInterrupt:
        print("\n\n aborted.")
        sys.exit(1)
