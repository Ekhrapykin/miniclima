#!/usr/bin/env python3
"""
miniClima EBC10 — CLI entry point.

Usage:
    python src/client.py --port /dev/ttyACM0 status
    python src/client.py --port /dev/ttyACM0 set-sp 55
    python src/client.py --port /dev/ttyACM0 start
    python src/client.py --port /dev/ttyACM0 -v vals
"""

import argparse
import logging
from enum import Enum

from ebc10 import Ebc10Client


class Cmd(str, Enum):
    STATUS       = "status"
    VALS         = "vals"
    SERNUM       = "sernum"
    DATE         = "date"
    TIME         = "time"
    OPHOURS      = "ophours"
    DUMP         = "dump"
    SET_SP       = "set-sp"
    SET_LOG_TIME = "set-log-time"
    SET_DATE     = "set-date"
    SET_TIME     = "set-time"
    START        = "start"
    STOP         = "stop"


def main():
    parser = argparse.ArgumentParser(description="miniClima EBC10 RS232 client")
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--baud", default=9600, type=int)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser(Cmd.STATUS,       help="Read sernum + vals")
    sub.add_parser(Cmd.VALS,         help="Read current sensor values")
    sub.add_parser(Cmd.SERNUM,       help="Read serial/firmware/settings")
    sub.add_parser(Cmd.DATE,         help="Read device date")
    sub.add_parser(Cmd.TIME,         help="Read device time")
    sub.add_parser(Cmd.OPHOURS,      help="Read operating hours")
    sub.add_parser(Cmd.DUMP,         help="Dump full history log (ASCII hex)")
    sub.add_parser(Cmd.START,        help="Start the unit")
    sub.add_parser(Cmd.STOP,         help="Stop the unit")

    p = sub.add_parser(Cmd.SET_SP,       help="Set humidity setpoint (%%)")
    p.add_argument("value", type=int)

    p = sub.add_parser(Cmd.SET_LOG_TIME, help="Set log interval (min)")
    p.add_argument("value", type=int)

    p = sub.add_parser(Cmd.SET_DATE,     help="Set date (DD.MM.YY)")
    p.add_argument("value")

    p = sub.add_parser(Cmd.SET_TIME,     help="Set time (HH:MM)")
    p.add_argument("value")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    with Ebc10Client(args.port, args.baud) as c:
        match Cmd(args.cmd):
            case Cmd.STATUS:
                s = c.read_sernum()
                v = c.read_vals()
                print(f"Serial:   {s.get('serial', '?')}  FW: {s.get('firmware', '?')}")
                print(f"Settings: SP={s.get('sp', '?')}%  LO={s.get('lo', '?')}%  "
                      f"HI={s.get('hi', '?')}%  HY={s.get('hy', '?')}  "
                      f"LT={s.get('lt', '?')}min  TO={s.get('to', '?')}")
                print(f"State:    {v.get('state', '?')}")
                if "rh" in v:
                    print(f"Sensor:   RH={v.get('rh', '?')}%  "
                          f"T1={v.get('t1', '?')}°C  T2={v.get('t2', '?')}°C  "
                          f"flag={v.get('flag') or 'none'}")

            case Cmd.VALS:
                print(c.read_vals())

            case Cmd.SERNUM:
                print(c.read_sernum())

            case Cmd.DATE:
                print(c.read_date())

            case Cmd.TIME:
                print(c.read_time())

            case Cmd.OPHOURS:
                print(f"{c.read_ophours()} hours")

            case Cmd.DUMP:
                print(c.dump())

            case Cmd.SET_SP:
                print("OK" if c.set_setpoint(args.value) else "FAIL")

            case Cmd.SET_LOG_TIME:
                print("OK" if c.set_log_time(args.value) else "FAIL")

            case Cmd.SET_DATE:
                print("OK" if c.set_date(args.value) else "FAIL")

            case Cmd.SET_TIME:
                print("OK" if c.set_time(args.value) else "FAIL")

            case Cmd.START:
                print("OK" if c.start() else "FAIL")

            case Cmd.STOP:
                print("OK" if c.stop() else "FAIL")


if __name__ == "__main__":
    main()
