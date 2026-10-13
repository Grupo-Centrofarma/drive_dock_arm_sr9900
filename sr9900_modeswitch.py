"""
Troca o CoreChip SR9900 do modo CD-ROM (USB\\VID_0FE6&PID_9910) para o modo
placa de rede (USB\\VID_0FE6&PID_9900).

Replica o que o install.exe oficial (x64) faz: envia o comando SCSI vendor 0xE0
via IOCTL_SCSI_PASS_THROUGH_DIRECT para a unidade "CoreChip USB CD-ROM".
Depois da troca, o driver Realtek RTL8152 ARM64 nativo do Windows
(rtuarm64w10.inf / rtucx21arm64.inf) pode ser usado para a placa de rede.

Uso (não precisa de Administrador):  python sr9900_modeswitch.py [LETRA]
"""
import ctypes
import ctypes.wintypes as wt
import string
import sys

IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x4D014
IOCTL_STORAGE_QUERY_PROPERTY = 0x2D1400
GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
FILE_SHARE_READ, FILE_SHARE_WRITE = 1, 2
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = wt.HANDLE(-1).value
SCSI_IOCTL_DATA_UNSPECIFIED = 2
DRIVE_CDROM = 5

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileW.restype = wt.HANDLE
k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
k32.DeviceIoControl.argtypes = [wt.HANDLE, wt.DWORD, ctypes.c_void_p, wt.DWORD,
                                ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
k32.CloseHandle.argtypes = [wt.HANDLE]


class SPTD(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.c_ushort),
        ("ScsiStatus", ctypes.c_ubyte),
        ("PathId", ctypes.c_ubyte),
        ("TargetId", ctypes.c_ubyte),
        ("Lun", ctypes.c_ubyte),
        ("CdbLength", ctypes.c_ubyte),
        ("SenseInfoLength", ctypes.c_ubyte),
        ("DataIn", ctypes.c_ubyte),
        ("DataTransferLength", ctypes.c_ulong),
        ("TimeOutValue", ctypes.c_ulong),
        ("DataBuffer", ctypes.c_void_p),
        ("SenseInfoOffset", ctypes.c_ulong),
        ("Cdb", ctypes.c_ubyte * 16),
    ]


class SPTDWithSense(ctypes.Structure):
    _fields_ = [("sptd", SPTD), ("Filler", ctypes.c_ulong), ("Sense", ctypes.c_ubyte * 32)]


def open_drive(letter):
    h = k32.CreateFileW(f"\\\\.\\{letter}:", GENERIC_READ | GENERIC_WRITE,
                        FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    if h == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    return h


def vendor_product(h):
    # STORAGE_PROPERTY_QUERY {StorageDeviceProperty=0, PropertyStandardQuery=0}
    query = (ctypes.c_ubyte * 12)()
    out = (ctypes.c_ubyte * 1024)()
    n = wt.DWORD()
    if not k32.DeviceIoControl(h, IOCTL_STORAGE_QUERY_PROPERTY, query, 12, out, 1024, ctypes.byref(n), None):
        return "", ""
    raw = bytes(out)

    def field(off_pos):
        off = int.from_bytes(raw[off_pos:off_pos + 4], "little")
        return raw[off:raw.index(b"\0", off)].decode(errors="ignore").strip() if off else ""

    # STORAGE_DEVICE_DESCRIPTOR: VendorIdOffset @12, ProductIdOffset @16
    return field(12), field(16)


def find_corechip_cd():
    for letter in string.ascii_uppercase:
        if k32.GetDriveTypeW(f"{letter}:\\") != DRIVE_CDROM:
            continue
        try:
            h = open_drive(letter)
        except OSError:
            continue
        vendor, product = vendor_product(h)
        k32.CloseHandle(h)
        if vendor in ("CoreChip", "Realtek") and "USB CD-ROM" in product:
            return letter
    return None


def switch(letter):
    h = open_drive(letter)
    try:
        s = SPTDWithSense()
        s.sptd.Length = ctypes.sizeof(SPTD)
        s.sptd.TargetId = 1
        s.sptd.CdbLength = 16
        s.sptd.SenseInfoLength = 24
        s.sptd.DataIn = SCSI_IOCTL_DATA_UNSPECIFIED
        s.sptd.TimeOutValue = 5
        s.sptd.SenseInfoOffset = SPTDWithSense.Sense.offset
        s.sptd.Cdb[0] = 0xE0  # comando vendor da CoreChip: sair do modo CD
        n = wt.DWORD()
        ok = k32.DeviceIoControl(h, IOCTL_SCSI_PASS_THROUGH_DIRECT, ctypes.byref(s), ctypes.sizeof(s),
                                 ctypes.byref(s), ctypes.sizeof(s), ctypes.byref(n), None)
        err = ctypes.get_last_error()
    finally:
        k32.CloseHandle(h)
    # O dispositivo costuma desconectar no meio do comando, então erro aqui não significa falha.
    print(f"DeviceIoControl ok={bool(ok)} lastError={err} scsiStatus={s.sptd.ScsiStatus}")


if __name__ == "__main__":
    letter = sys.argv[1].rstrip(":").upper() if len(sys.argv) > 1 else find_corechip_cd()
    if not letter:
        sys.exit("Unidade 'CoreChip USB CD-ROM' não encontrada (já está em modo rede?).")
    print(f"Enviando comando de troca de modo para {letter}:")
    switch(letter)
