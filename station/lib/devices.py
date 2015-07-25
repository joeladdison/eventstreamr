import os
import glob
import re
import subprocess

# Regular expressions
ALSA_DEVICE_REGEX = re.compile(r'].+USB Audio (CODEC|Device)')
CARD_ID_REGEX = re.compile(r'^.+(?P<card> \d+).*', re.X)
LSUSB_REGEX = re.compile(
    r'^(?P<vid> [^+s]{4}).(?P<did> [^+s]{4})$', re.I | re.X)
LSUSB_NAME_REGEX = re.compile(
    r'^Bus.\d+.Device.\d+:.ID.[^+s]{4}:[^+s]{4}.(?P<name>.+)', re.I | re.X)
LSPCI_REGEX = re.compile(r'..:..\...(?P<name>.+)', re.I | re.X)
V4L_USB_REGEX = re.compile(
    r'\/dev\/v4l\/by-id\/usb-(?P<name> .+)-video-index\d', re.I | re.X)
V4L_USB_ID_REGEX = re.compile(r'^[^+s]{4}_[^+s]{4}$', re.I | re.X)
V4L_PCI_REGEX = re.compile(
    r'pci-[^+s]{4}:(?P<pciid>..:..\..)-video-index\d', re.I | re.X)


def all():
    v4l_devices = v4l()
    dv_devices = dv()
    alsa_devices = alsa()
    devices = {
        'v4l': {'all': v4l_devices},
        'dv': {'all': dv_devices},
        'alsa': {'all': alsa_devices},
        'array': v4l_devices + dv_devices + alsa_devices,
    }
    # TODO: add 'all' and 'array' sections
    return devices


def v4l():
    found_devices = glob.glob('/dev/video*')
    devices = []
    for device in found_devices:
        identifier = device[5:]
        info = {
            'device': device,
            'name': get_v4l_name(identifier),
            'type': 'v4l',
            'id': identifier
        }
        devices.append(info)
    return devices


def dv():
    found_devices = glob.glob('/sys/bus/firewire/devices/*')
    devices = []
    for device_path in found_devices:
        vendor = os.path.join(device_path, 'vendor')
        if os.path.exists(vendor):
            with open(vendor, 'r') as f:
                vendor_name = f.readline().strip()

            vendor_name_path = os.path.join(device_path, 'vendor_name')
            if os.path.exists(vendor_name_path):
                with open(vendor_name_path, 'r') as f:
                    vendor_name = f.readline().strip()

            if vendor_name == '0x002011':
                vendor_name = 'Canopus'

            if vendor_name != 'Linux Firewire':
                guid_path = os.path.join(device_path, 'guid')
                with open(guid_path, 'r') as f:
                    guid = f.readline().strip()

                model = 'unknown'
                if vendor_name == 'Canopus':
                    model = 'twinpact100'
                model_name_path = os.path.join(device_path, 'model_name')
                if os.path.exists(model_name_path):
                    with open(model_name_path, 'r') as f:
                        model = f.readline().strip()
                device = {
                    'device': guid,
                    'model': model,
                    'name': "{0} {1}".format(vendor_name, model),
                    'type': 'dv',
                    'id': guid,
                    'path': guid_path
                }
                devices.append(device)
    return devices


def alsa():
    """
    Only Does USB devices currently
    """
    devices = []
    if not os.path.exists('/proc/asound/cards'):
        return devices

    with open('/proc/asound/cards', 'r') as f:
        found_devices = filter(ALSA_DEVICE_REGEX.search, f)
    for d in found_devices:
        card = CARD_ID_REGEX.search(d).group('card')
        usbid_path = '/proc/asound/card{0}/usbid'.format(card)
        with open(usbid_path, 'r') as f:
            usbid = f.readline().strip()
        name = name_lsusb(usbid)

        device = {
            'id': usbid,
            'name': name,
            'device': card,
            'type': 'alsa',
            'alsa': card,
        }
        devices.append(device)
    return devices


def get_v4l_name(device):
    # Find USB
    usbs = glob.glob('/dev/v4l/by-id/*')
    for usb in usbs:
        if os.path.realpath(usb) == device:
            name = V4L_USB_REGEX.search(usb).group('name')

            # Some lesser known devices present an ID instead of a name
            out = V4L_USB_ID_REGEX.search(name)
            if out:
                return name_lsusb(name)
            return name.replace('_', ' ')

    # Find PCI
    pcis = glob.glob('/dev/v4l/by-path/*')
    for pci in pcis:
        if os.path.realpath(pci) == device:
            pci_id = V4L_PCI_REGEX.search(pci).group('pciid')
            return name_lspci(pci_id)


def name_lsusb(name):
    ids = LSUSB_REGEX.search(name)
    lsusb_command = 'lsusb | grep "{vid}:{did}"'.format(**ids.groupdict())
    output = subprocess.check_output(lsusb_command, shell=True)
    return LSUSB_NAME_REGEX.search(output).group('name')


def name_lspci(name):
    lspci_command = 'lspci | grep "{0}"'.format(name)
    output = subprocess.check_output(lspci_command, shell=True)
    return LSPCI_REGEX.search(output).group('name')
