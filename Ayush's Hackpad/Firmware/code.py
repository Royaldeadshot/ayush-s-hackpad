import board
import time
import digitalio
import displayio
import busio
import neopixel

from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC
from kmk.handlers.sequences import simple_key_sequence
from kmk.extensions.media_keys import MediaKeys
from kmk.extensions.rgb import RGB
from kmk.modules.encoder import EncoderHandler

# ---------- PIN MAP ----------
# Buttons (to GND, internal pullups enabled)
SW1 = board.GP26
SW2 = board.GP27
SW3 = board.GP28
SW4 = board.GP29

# Encoder
ENC_A = board.GP3
ENC_B = board.GP4
ENC_BTN = board.GP2

# OLED I2C
SDA = board.GP6
SCL = board.GP7

# LEDs
LED_PIN = board.GP0
LED_COUNT = 8

# ---------- KMK SETUP ----------
keyboard = KMKKeyboard()
keyboard.modules.append(MediaKeys())

encoders = EncoderHandler()
keyboard.modules.append(encoders)

# ---------- LEDS ----------
pixels = neopixel.NeoPixel(LED_PIN, LED_COUNT, brightness=0.25, auto_write=False)

led_modes = [
    'off',
    'white',
    'rainbow',
]

current_mode = 0

def set_led_mode(mode):
    global current_mode
    current_mode = mode % len(led_modes)

    if led_modes[current_mode] == 'off':
        pixels.fill((0, 0, 0))

    elif led_modes[current_mode] == 'white':
        pixels.fill((255, 255, 255))

    elif led_modes[current_mode] == 'rainbow':
        for i in range(LED_COUNT):
            pixels[i] = (
                (i * 30) % 255,
                (120 + i * 15) % 255,
                (200 + i * 10) % 255,
            )

    pixels.show()

set_led_mode(0)

# ---------- OLED ----------
displayio.release_displays()
i2c = busio.I2C(SCL, SDA)
import adafruit_displayio_ssd1306
display_bus = displayio.I2CDisplay(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=32)

# idle animation frames (simple bars)
frames = []
for h in range(4, 28, 6):
    bmp = displayio.Bitmap(128, 32, 2)
    pal = displayio.Palette(2)
    pal[0] = 0x000000
    pal[1] = 0xFFFFFF
    for x in range(0, 128, 4):
        for y in range(32 - h, 32):
            bmp[x, y] = 1
    frames.append(displayio.TileGrid(bmp, pixel_shader=pal))

splash = displayio.Group()
display.show(splash)

frame_index = 0
last_anim = time.monotonic()
anim_interval = 0.15
showing_volume = False
volume_timeout = 1.2
volume_timestamp = 0
current_volume_level = 10   # fake visual bar only

def draw_volume_bar(level):
    global splash, showing_volume
    splash = displayio.Group()
    display.show(splash)

    bmp = displayio.Bitmap(128, 32, 2)
    pal = displayio.Palette(2)
    pal[0] = 0x000000
    pal[1] = 0xFFFFFF

    width = int((level / 20) * 120)
    for x in range(width):
        for y in range(12, 20):
            bmp[x + 4, y] = 1

    splash.append(displayio.TileGrid(bmp, pixel_shader=pal))
    showing_volume = True


def update_animation():
    global frame_index, last_anim, showing_volume
    if showing_volume:
        return
    if time.monotonic() - last_anim > anim_interval:
        splash.pop() if len(splash) else None
        splash.append(frames[frame_index])
        frame_index = (frame_index + 1) % len(frames)
        last_anim = time.monotonic()


# ---------- BUTTONS ----------
keyboard.keymap = [
    [
        # SW1 – open Chrome (Win+R then "chrome")
        simple_key_sequence((KC.LGUI, KC.R)),
        KC.LCTL(KC.C),  # SW2 copy
        KC.LCTL(KC.V),  # SW3 paste

        KC.NO,          # we'll override in process() for LED mode
    ]
]

# pull-ups
for pin in (SW1, SW2, SW3, SW4):
    btn = digitalio.DigitalInOut(pin)
    btn.direction = digitalio.Direction.INPUT
    btn.pull = digitalio.Pull.UP

# ---------- ENCODER ----------
encoders.pins = (
    (ENC_A, ENC_B, None, False),
)

# when encoder turns
@encoders.handler
def rotate(encoder, state):
    global current_volume_level, volume_timestamp
    if state > 0:
        keyboard.send(KC.VOLU)
        current_volume_level = min(20, current_volume_level + 1)
    else:
        keyboard.send(KC.VOLD)
        current_volume_level = max(0, current_volume_level - 1)

    draw_volume_bar(current_volume_level)
    volume_timestamp = time.monotonic()

# encoder push
enc_btn = digitalio.DigitalInOut(ENC_BTN)
enc_btn.direction = digitalio.Direction.INPUT
enc_btn.pull = digitalio.Pull.UP

# ---------- MAIN LOOP ----------
while True:
    keyboard.update()

    # encoder button
    if not enc_btn.value:
        keyboard.send(KC.MPLY)
        time.sleep(0.2)

    # LED mode key (SW4)
    if not digitalio.DigitalInOut(SW4).value:
        set_led_mode(current_mode + 1)
        time.sleep(0.25)

    # hide volume after timeout
    if showing_volume and (time.monotonic() - volume_timestamp) > volume_timeout:
        showing_volume = False
        splash = displayio.Group()
        display.show(splash)

    update_animation()
    time.sleep(0.01)
