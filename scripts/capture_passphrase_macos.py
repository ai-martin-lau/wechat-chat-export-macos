#!/usr/bin/env python3
"""Capture and HMAC-verify a WeChat 4.1+ WCDB passphrase with LLDB."""

import argparse
import hashlib
import hmac
import json
import os
import struct
import sys
from pathlib import Path


PAGE_SIZE = 4096
RESERVE_SIZE = 80


def derive_key(passphrase, salt):
    return hashlib.pbkdf2_hmac("sha512", passphrase, salt, 256000, dklen=32)


def verify_derived_key(key, page):
    if len(page) < PAGE_SIZE:
        return False
    salt = page[:16]
    mac_salt = bytes(value ^ 0x3A for value in salt)
    mac_key = hashlib.pbkdf2_hmac("sha512", key, mac_salt, 2, dklen=32)
    signed = page[16 : PAGE_SIZE - RESERVE_SIZE + 16]
    expected = page[PAGE_SIZE - 64 : PAGE_SIZE]
    verifier = hmac.new(mac_key, signed, hashlib.sha512)
    verifier.update(struct.pack("<I", 1))
    return hmac.compare_digest(verifier.digest(), expected)


def read_pointer(process, address, error):
    value = process.ReadPointerFromMemory(address, error)
    return value if error.Success() else 0


def candidate_passphrases(process, frame, error):
    x1 = frame.FindRegister("x1").GetValueAsUnsigned()
    x2 = frame.FindRegister("x2").GetValueAsUnsigned()
    print(f"[*] Breakpoint hit; candidate length={x2}")

    if x1 and x2 == 32:
        data = process.ReadMemory(x1, 32, error)
        if error.Success() and len(data) == 32:
            yield "direct", bytes(data)

    if x1:
        size = read_pointer(process, x1 + 16, error)
        pointer = read_pointer(process, x1 + 8, error)
        if size == 32 and pointer:
            data = process.ReadMemory(pointer, 32, error)
            if error.Success() and len(data) == 32:
                yield "structure", bytes(data)


def save_result(output, passphrase, derived_key, salt, hook, uid, gid):
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "passphrase": passphrase.hex(),
        "message_key": derived_key.hex(),
        "salt": salt.hex(),
        "hook_file_address": hex(hook),
    }
    with output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    if uid is not None:
        os.chown(output, uid, gid if gid is not None else -1)
    os.chmod(output, 0o600)


def capture(args):
    try:
        import lldb
    except ImportError as exc:
        raise RuntimeError(
            "Could not import lldb; run with PYTHONPATH=$(lldb -P) and Xcode Python"
        ) from exc

    with args.verify_db.open("rb") as handle:
        page = handle.read(PAGE_SIZE)
    if len(page) != PAGE_SIZE:
        raise RuntimeError(f"Verification database is too small: {args.verify_db}")
    salt = page[:16]

    debugger = lldb.SBDebugger.Create()
    debugger.SetAsync(False)
    target = debugger.CreateTarget(str(args.binary))
    if not target.IsValid():
        raise RuntimeError(f"Could not create LLDB target: {args.binary}")
    module = target.GetModuleAtIndex(0)
    hook_address = module.ResolveFileAddress(args.hook)
    if not hook_address.IsValid():
        raise RuntimeError(f"Could not resolve hook address: {args.hook:#x}")
    breakpoint = target.BreakpointCreateBySBAddress(hook_address)
    action = "running WeChat" if args.attach_existing else "next WeChat launch"
    print(
        f"[*] Waiting for {action}; hook={args.hook:#x}, "
        f"locations={breakpoint.GetNumLocations()}"
    )

    error = lldb.SBError()
    process = target.AttachToProcessWithName(
        debugger.GetListener(), "WeChat", not args.attach_existing, error
    )
    if not error.Success():
        raise RuntimeError(f"Attach failed: {error.GetCString()}")
    print(f"[+] Attached to PID {process.GetProcessID()}")

    try:
        while True:
            process.Continue()
            state = process.GetState()
            if state in (lldb.eStateExited, lldb.eStateCrashed, lldb.eStateDetached):
                raise RuntimeError(f"WeChat stopped before capture: state={state}")
            hit_thread = None
            for index in range(process.GetNumThreads()):
                thread = process.GetThreadAtIndex(index)
                if thread.GetStopReason() == lldb.eStopReasonBreakpoint:
                    hit_thread = thread
                    break
            if hit_thread is None:
                continue
            frame = hit_thread.GetFrameAtIndex(0)
            for method, passphrase in candidate_passphrases(process, frame, error):
                derived_key = derive_key(passphrase, salt)
                if verify_derived_key(derived_key, page):
                    save_result(
                        args.output,
                        passphrase,
                        derived_key,
                        salt,
                        args.hook,
                        args.output_uid,
                        args.output_gid,
                    )
                    print(f"[+] Verified via {method}; secret saved with mode 0600")
                    return
            print("[!] Candidate did not verify; continuing")
    finally:
        if process.IsValid() and process.GetState() not in (
            lldb.eStateExited,
            lldb.eStateDetached,
        ):
            process.Detach()
        lldb.SBDebugger.Destroy(debugger)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--hook", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--verify-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-uid", type=int)
    parser.add_argument("--output-gid", type=int)
    parser.add_argument("--attach-existing", action="store_true")
    return parser.parse_args()


def main():
    capture(parse_args())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[-] {exc}", file=sys.stderr)
        raise SystemExit(1)

