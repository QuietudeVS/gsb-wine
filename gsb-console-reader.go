// gsb-console-reader is a read-only diagnostic for the Wine MZ server console.
// It attaches to the console used by MZServerConsole.exe, reads the last few
// lines from its Windows console buffer, and writes plain UTF-8 text to /tmp.
// It does not send input, stop processes, or change server configuration.
package main

import (
    "fmt"
    "os"
    "strings"
    "syscall"
    "unicode/utf16"
    "unsafe"
)

const (
    th32csSnapProcess = 0x00000002
    genericRead = 0x80000000
    genericWrite = 0x40000000
    fileShareRead = 0x00000001
    fileShareWrite = 0x00000002
    openExisting = 3
)

type processEntry32 struct {
    Size uint32
    Usage uint32
    ProcessID uint32
    DefaultHeapID uintptr
    ModuleID uint32
    Threads uint32
    ParentProcessID uint32
    PriClassBase int32
    Flags uint32
    ExeFile [260]uint16
}

type coord struct{ X, Y int16 }
type smallRect struct{ Left, Top, Right, Bottom int16 }
type screenInfo struct{
    Size coord
    Cursor coord
    Attributes uint16
    Window smallRect
    MaximumWindowSize coord
}

var (
    k32 = syscall.NewLazyDLL("kernel32.dll")
    pSnapshot = k32.NewProc("CreateToolhelp32Snapshot")
    pFirst = k32.NewProc("Process32FirstW")
    pNext = k32.NewProc("Process32NextW")
    pClose = k32.NewProc("CloseHandle")
    pAttach = k32.NewProc("AttachConsole")
    pFree = k32.NewProc("FreeConsole")
    pCreate = k32.NewProc("CreateFileW")
    pInfo = k32.NewProc("GetConsoleScreenBufferInfo")
    pRead = k32.NewProc("ReadConsoleOutputCharacterW")
)

func winError(label string, err error) error {
    return fmt.Errorf("%s: %v", label, err)
}

func findConsolePID() (uint32, error) {
    snap, _, e := pSnapshot.Call(th32csSnapProcess, 0)
    if snap == ^uintptr(0) { return 0, winError("CreateToolhelp32Snapshot", e) }
    defer pClose.Call(snap)

    var pe processEntry32
    pe.Size = uint32(unsafe.Sizeof(pe))
    r, _, e := pFirst.Call(snap, uintptr(unsafe.Pointer(&pe)))
    if r == 0 { return 0, winError("Process32FirstW", e) }
    var pid uint32
    count := 0
    for {
        name := syscall.UTF16ToString(pe.ExeFile[:])
        if strings.EqualFold(name, "MZServerConsole.exe") {
            pid = pe.ProcessID
            count++
        }
        r, _, _ = pNext.Call(snap, uintptr(unsafe.Pointer(&pe)))
        if r == 0 { break }
    }
    if count == 0 { return 0, fmt.Errorf("MZServerConsole.exe not found in Wine process list") }
    if count > 1 { return 0, fmt.Errorf("found %d MZServerConsole.exe processes; refusing to guess", count) }
    return pid, nil
}

func readConsole() (string, error) {
    pid, err := findConsolePID()
    if err != nil { return "", err }

    r, _, e := pAttach.Call(uintptr(pid))
    if r == 0 { return "", winError(fmt.Sprintf("AttachConsole(PID %d)", pid), e) }
    defer pFree.Call()

    path, err := syscall.UTF16PtrFromString("CONOUT$")
    if err != nil { return "", err }
    h, _, e := pCreate.Call(uintptr(unsafe.Pointer(path)), genericRead|genericWrite,
        fileShareRead|fileShareWrite, 0, openExisting, 0, 0)
    if h == ^uintptr(0) { return "", winError("CreateFileW(CONOUT$)", e) }
    defer pClose.Call(h)

    var info screenInfo
    r, _, e = pInfo.Call(h, uintptr(unsafe.Pointer(&info)))
    if r == 0 { return "", winError("GetConsoleScreenBufferInfo", e) }
    width := int(info.Size.X)
    height := int(info.Size.Y)
    if width <= 0 || width > 1000 || height <= 0 { return "", fmt.Errorf("invalid console buffer dimensions %dx%d", width, height) }

    last := int(info.Cursor.Y)
    if int(info.Window.Bottom) > last { last = int(info.Window.Bottom) }
    if last >= height { last = height - 1 }
    first := last - 89
    if first < 0 { first = 0 }
    var lines []string
    for y := first; y <= last; y++ {
        cells := make([]uint16, width)
        var nread uint32
        position := uint32(y) << 16
        r, _, e = pRead.Call(h, uintptr(unsafe.Pointer(&cells[0])), uintptr(uint32(width)), uintptr(position), uintptr(unsafe.Pointer(&nread)))
        if r == 0 { return "", winError(fmt.Sprintf("ReadConsoleOutputCharacterW(row %d)", y), e) }
        if nread > uint32(width) { nread = uint32(width) }
        line := string(utf16.Decode(cells[:nread]))
        line = strings.TrimRight(line, " \t\x00\r\n")
        lines = append(lines, line)
    }
    // Trim blank-only lines from both ends, keep interior spacing intact.
    for len(lines) > 0 && lines[0] == "" { lines = lines[1:] }
    for len(lines) > 0 && lines[len(lines)-1] == "" { lines = lines[:len(lines)-1] }
    return fmt.Sprintf("MZ Server Console [Wine PID %d], buffer %dx%d\n%s\n", pid, width, height, strings.Join(lines, "\n")), nil
}

func main() {
    output := `Z:\tmp\gsb-console-text.txt`
    if len(os.Args) > 1 { output = os.Args[1] }
    result, err := readConsole()
    if err != nil {
        result = "ERROR: " + err.Error() + "\n"
    }
    if e := os.WriteFile(output, []byte(result), 0600); e != nil { os.Exit(3) }
    if err != nil { os.Exit(2) }
}
