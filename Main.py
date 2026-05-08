#!/usr/bin/env python3
from __future__ import annotations
import os, sys, shlex, subprocess, shutil, stat, time, traceback
from datetime import datetime

WINDOW_TITLE = "termux"
HOME = os.path.expanduser("~")
ENV = os.environ.copy()
HISTORY: list[str] = []
ALIASES: dict[str,str] = {"ll": "ls -la"}
PROMPT_HOST = "kali"
LOG_FILE = os.path.join(HOME, "termux_error.log")

def set_title(title: str) -> None:
    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        else:
            sys.stdout.write(f"\x1b]2;{title}\x07")
    except Exception:
        pass

set_title(WINDOW_TITLE)

def human_size(n: int) -> str:
    for u in ("B","K","M","G","T"):
        if abs(n) < 1024.0:
            return f"{n:.0f}{u}"
        n /= 1024.0
    return f"{n:.0f}P"

def color(s: str, code: str) -> str:
    return f"\x1b[{code}m{s}\x1b[0m"

def cmd_ls(args: list[str]) -> None:
    import argparse
    p = argparse.ArgumentParser(prog="ls", add_help=False)
    p.add_argument("-l", action="store_true")
    p.add_argument("-a", action="store_true")
    p.add_argument("-h", dest="human", action="store_true")
    p.add_argument("paths", nargs="*", default=["."])
    try:
        ns = p.parse_args(args)
    except SystemExit:
        print("ls: invalid args"); return
    for path in ns.paths:
        try:
            names = os.listdir(path)
        except Exception as e:
            print(f"ls: cannot access '{path}': {e}"); continue
        if not ns.a:
            names = [n for n in names if not n.startswith('.')]
        names.sort()
        if ns.l:
            for name in names:
                pth = os.path.join(path, name)
                try:
                    st = os.lstat(pth)
                except Exception:
                    print(name); continue
                mode = stat.filemode(st.st_mode)
                nlink = st.st_nlink
                owner = getattr(st, "st_uid", "?")
                size = human_size(st.st_size) if ns.human else str(st.st_size)
                mtime = datetime.fromtimestamp(st.st_mtime).strftime("%b %d %H:%M")
                if os.path.isdir(pth):
                    namec = color(name,"34")
                elif os.access(pth, os.X_OK):
                    namec = color(name,"32")
                else:
                    namec = name
                print(f"{mode} {nlink} {owner} {size:>6} {mtime} {namec}")
        else:
            out = []
            for name in names:
                pth = os.path.join(path, name)
                if os.path.isdir(pth):
                    out.append(color(name,"34"))
                elif os.access(pth, os.X_OK):
                    out.append(color(name,"32"))
                else:
                    out.append(name)
            print("  ".join(out))

def cmd_pwd(a): print(os.getcwd())
def cmd_cd(args):
    t = args[0] if args else HOME
    try: os.chdir(os.path.expanduser(t))
    except Exception as e: print(f"cd: {e}")
def cmd_cat(args):
    if not args: print("cat: missing file"); return
    for f in args:
        try:
            with open(f, "r", encoding="utf-8", errors="replace") as fh:
                sys.stdout.write(fh.read())
        except Exception as e:
            print(f"cat: {f}: {e}")
def cmd_cp(args):
    if len(args) < 2: print("cp: missing destination"); return
    srcs, dest = args[:-1], args[-1]
    try:
        if len(srcs)>1 and not os.path.isdir(dest):
            print(f"cp: target '{dest}' is not a directory"); return
        for s in srcs: shutil.copy(s, dest)
    except Exception as e: print(f"cp: {e}")
def cmd_mv(args):
    if len(args) < 2: print("mv: missing destination"); return
    for s in args[:-1]:
        try: shutil.move(s, args[-1])
        except Exception as e: print(f"mv: {e}")
def cmd_rm(args):
    if not args: print("rm: missing operand"); return
    force=False; rec=False; files=[]
    for a in args:
        if a in ("-f","--force"): force=True
        elif a in ("-r","-R","--recursive"): rec=True
        else: files.append(a)
    for f in files:
        try:
            if os.path.isdir(f) and rec: shutil.rmtree(f)
            elif os.path.isdir(f): print(f"rm: cannot remove '{f}': is a directory")
            else: os.remove(f)
        except Exception as e:
            if not force: print(f"rm: cannot remove '{f}': {e}")
def cmd_clear(a): os.system("cls" if os.name=="nt" else "clear")
def cmd_echo(a): print(" ".join(a))
def cmd_grep(args, input_text=None):
    import re
    if not args: print("grep: missing pattern"); return
    pat=args[0]; files=args[1:]; r=re.compile(pat)
    if not files:
        if input_text is not None:
            for L in input_text.splitlines():
                if r.search(L): print(L)
        else:
            for L in sys.stdin:
                if r.search(L): print(L, end="")
        return
    for fname in files:
        try:
            with open(fname, "r", encoding="utf-8", errors="replace") as fh:
                for i, L in enumerate(fh,1):
                    if r.search(L): print(f"{fname}:{i}:{L}", end="")
        except Exception as e: print(f"grep: {fname}: {e}")
def cmd_whoami(a): print(os.environ.get("USER") or os.environ.get("USERNAME") or "user")
def cmd_uname(a):
    try:
        import platform
        u=platform.uname(); print(f"{u.system} {u.release}")
    except: print("Unix-like")
def cmd_head(args):
    n=10; files=args or ["-"]
    if args and args[0].startswith("-n"):
        try: n=int(args[0][2:]); files=args[1:]
        except: files=args[1:]
    for fn in files:
        if fn=="-":
            for i,L in enumerate(sys.stdin):
                if i>=n: break
                print(L, end="")
        else:
            try:
                with open(fn,"r",encoding="utf-8",errors="replace") as fh:
                    for i,L in enumerate(fh):
                        if i>=n: break
                        print(L, end="")
            except Exception as e: print(f"head: {fn}: {e}")
def cmd_tail(args):
    n=10; files=args or ["-"]
    if args and args[0].startswith("-n"):
        try: n=int(args[0][2:]); files=args[1:]
        except: files=args[1:]
    for fn in files:
        if fn=="-":
            Ls=sys.stdin.read().splitlines()
            for L in Ls[-n:]: print(L)
        else:
            try:
                with open(fn,"r",encoding="utf-8",errors="replace") as fh:
                    Ls=fh.read().splitlines()
                    for L in Ls[-n:]: print(L)
            except Exception as e: print(f"tail: {fn}: {e}")
def cmd_touch(args):
    if not args: print("touch: missing file"); return
    for f in args:
        try:
            with open(f,"a"): os.utime(f, None)
        except Exception as e: print(f"touch: {e}")
def cmd_chmod(args):
    if len(args)<2: print("chmod: missing"); return
    try: mode=int(args[0],8)
    except: print("chmod: invalid mode"); return
    for f in args[1:]:
        try: os.chmod(f, mode)
        except Exception as e: print(f"chmod: {f}: {e}")
def cmd_mkdir(args):
    for d in args:
        try: os.makedirs(d, exist_ok=True)
        except Exception as e: print(f"mkdir: {d}: {e}")
def cmd_rmdir(args):
    for d in args:
        try: os.rmdir(d)
        except Exception as e: print(f"rmdir: {d}: {e}")
def cmd_history(a):
    for i,c in enumerate(HISTORY,1): print(f"{i}  {c}")
def cmd_alias(args):
    if not args:
        for k,v in ALIASES.items(): print(f"alias {k}='{v}'"); return
    for a in args:
        if "=" in a:
            k,v=a.split("=",1); v=v.strip("'\""); ALIASES[k]=v
        else: print("alias: use name='command'")
def cmd_env(a):
    for k,v in ENV.items(): print(f"{k}={v}")
def cmd_setenv(args):
    if len(args)!=2: print("setenv: KEY VALUE"); return
    ENV[args[0]]=args[1]
def cmd_unsetenv(args):
    for k in args: ENV.pop(k, None)
def cmd_which(args):
    for a in args:
        p=shutil.which(a)
        print(p if p else f"{a}: not found")
def cmd_top(a):
    print("top: limited mode (install psutil for better output)")
def cmd_exit(a): raise SystemExit

BUILTINS = {
 "ls":cmd_ls,"ll":lambda a:cmd_ls(["-l","-a"]+a),"pwd":cmd_pwd,"cd":cmd_cd,
 "cat":cmd_cat,"cp":cmd_cp,"mv":cmd_mv,"rm":cmd_rm,"clear":cmd_clear,
 "echo":cmd_echo,"grep":cmd_grep,"whoami":cmd_whoami,"uname":cmd_uname,
 "head":cmd_head,"tail":cmd_tail,"touch":cmd_touch,"chmod":cmd_chmod,
 "mkdir":cmd_mkdir,"rmdir":cmd_rmdir,"history":cmd_history,"alias":cmd_alias,
 "env":cmd_env,"setenv":cmd_setenv,"unsetenv":cmd_unsetenv,"which":cmd_which,
 "top":cmd_top,"exit":cmd_exit,"quit":cmd_exit
}

def run_external(cmd,args,input_bytes=None,stdout_target=None,append=False):
    try:
        proc=subprocess.Popen([cmd]+args, stdin=subprocess.PIPE if input_bytes is not None else None,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV)
        out,err=proc.communicate(input_bytes)
        if stdout_target:
            mode="ab" if append else "wb"
            with open(stdout_target,mode) as f: f.write(out)
        else:
            try: sys.stdout.buffer.write(out)
            except: sys.stdout.write(out.decode(errors="replace"))
        if err:
            try: sys.stderr.buffer.write(err)
            except: sys.stderr.write(err.decode(errors="replace"))
        return proc.returncode or 0
    except FileNotFoundError:
        print(f"{cmd}: command not found"); return 127
    except Exception as e:
        print(f"Error running {cmd}: {e}"); return 1

def execute_segment(cmd_name,args,input_text=None,stdout_target=None,append=False):
    if cmd_name in BUILTINS:
        try:
            if cmd_name=="grep":
                from io import StringIO
                old=sys.stdout; sio=StringIO(); sys.stdout=sio
                try: BUILTINS[cmd_name](args,input_text)  # type: ignore[arg-type]
                finally: sys.stdout=old
                out=sio.getvalue()
                if stdout_target:
                    mode="a" if append else "w"
                    with open(stdout_target,mode,encoding="utf-8") as f: f.write(out)
                    return 0,""
                return 0,out
            else:
                if stdout_target is not None:
                    from io import StringIO
                    old=sys.stdout; sio=StringIO(); sys.stdout=sio
                    try: BUILTINS[cmd_name](args)
                    finally: sys.stdout=old
                    mode="a" if append else "w"
                    with open(stdout_target,mode,encoding="utf-8") as f: f.write(sio.getvalue())
                    return 0,""
                elif input_text is not None:
                    from io import StringIO
                    old=sys.stdout; sio=StringIO(); sys.stdout=sio
                    try: BUILTINS[cmd_name](args)
                    finally: sys.stdout=old
                    return 0,sio.getvalue()
                else:
                    BUILTINS[cmd_name](args); return 0,""
        except SystemExit:
            raise
        except Exception as e:
            print(f"{cmd_name}: {e}"); return 1,""
    input_bytes = input_text.encode() if input_text is not None else None
    rc = run_external(cmd_name,args,input_bytes=input_bytes,stdout_target=stdout_target,append=append)
    return rc, ""

def parse_and_run(line: str) -> None:
    if not line.strip(): return
    HISTORY.append(line)
    try:
        parts = shlex.split(line, posix=(os.name!="nt"))
    except Exception:
        parts=line.split()
    if not parts: return
    if parts[0] in ALIASES:
        expanded = shlex.split(ALIASES[parts[0]]) + parts[1:]
        line = " ".join(shlex.quote(p) for p in expanded)
    segments = [s.strip() for s in line.split("|")]
    input_text=None
    for i,seg in enumerate(segments):
        out_file=None; append=False
        if ">>" in seg:
            left,right=seg.split(">>",1); seg=left.strip(); out_file=right.strip().split()[0] if right.strip() else None; append=True
        elif ">" in seg:
            left,right=seg.split(">",1); seg=left.strip(); out_file=right.strip().split()[0] if right.strip() else None; append=False
        try: seg_parts=shlex.split(seg, posix=(os.name!="nt"))
        except Exception: seg_parts=seg.split()
        if not seg_parts: continue
        cmd_name, *args = seg_parts
        if cmd_name in ALIASES:
            expanded = shlex.split(ALIASES[cmd_name]) + args
            cmd_name, *args = expanded
        stdout_target = out_file if (i==len(segments)-1 and out_file) else None
        rc,out = execute_segment(cmd_name,args,input_text=input_text,stdout_target=stdout_target,append=append)
        if rc!=0: break
        if i < len(segments)-1:
            if out: input_text = out
            else:
                try:
                    proc=subprocess.Popen([cmd_name]+args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          stdin=subprocess.PIPE if input_text else None, env=ENV)
                    o,e=proc.communicate(input_text.encode() if input_text else None)
                    input_text = o.decode(errors="replace")
                except FileNotFoundError:
                    print(f"{cmd_name}: command not found"); input_text=""; break
                except Exception as e:
                    print(f"pipeline error: {e}"); input_text=""; break

def prompt() -> str:
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "user"
    cwd = os.getcwd()
    if cwd.startswith(HOME): cwd = "~"+cwd[len(HOME):]
    sym = "#" if user=="root" else "$"
    return f"\x1b[31m{user}\x1b[0m@\x1b[34m{PROMPT_HOST}\x1b[0m:\x1b[33m{cwd}\x1b[0m{sym} "

def main_loop():
    while True:
        try:
            line = input(prompt())
        except EOFError:
            print(); break
        except KeyboardInterrupt:
            print(); continue
        try:
            parse_and_run(line)
        except SystemExit:
            raise
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    try:
        main_loop()
    except SystemExit:
        pass
    except Exception as exc:
        try:
            with open(LOG_FILE,"a",encoding="utf-8") as f:
                f.write("\n\n--- "+time.ctime()+" ---\n")
                f.write("Unhandled exception:\n")
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)
        except Exception:
            pass
        print("A fatal error occurred. See", LOG_FILE)
        try: input()
        except Exception: time.sleep(2)
