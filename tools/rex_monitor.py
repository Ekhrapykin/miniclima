import serial, datetime, time
ser = serial.Serial('/dev/ttyACM0', 9600, timeout=5)
print('Monitoring raw serial... change settings on panel now.')
print('Running for 90 seconds.')
print('---')
end = time.time() + 90
while time.time() < end:
    data = ser.read(ser.in_waiting or 1)
    if data:
        ts = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
        hex_str = ' '.join(f'{b:02X}' for b in data)
        ascii_safe = data.decode('ascii', errors='replace').replace('\r','\\\\r').replace('\n','\\\\n')
        print(f'{ts} HEX: {hex_str}  ASCII: {ascii_safe}')
print('--- done ---')
ser.close()