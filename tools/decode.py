import logging

import ebc10  # (Assuming this is your import)


def main():
    # 1. Configure the logging system to output DEBUG level and above
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    with open("../captures/raw_dump_2.txt", "r") as f:
        hex_str = f.read().strip()
    records = ebc10.parse_dump_records(bytearray.fromhex(hex_str))

    for r in records:
        ts_str = r["ts"].strftime("%Y-%m-%d %H:%M") if r["ts"] else "no-ts      "
        print(f"{ts_str}  {r['type']:<12}  {r['data']}")


if __name__ == "__main__":
    main()