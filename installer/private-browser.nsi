; Private Browser NSIS installer
!define APPNAME "Private Browser"
!define COMPANYNAME "private-browser"
!define DESCRIPTION "Anti-detect browser manager"
!define VERSIONMAJOR 0
!define VERSIONMINOR 6
!define VERSIONBUILD 0
!define HELPURL "https://github.com/dtkoe/private-browser"

RequestExecutionLevel user
InstallDir "$LOCALAPPDATA\${COMPANYNAME}"
Name "${APPNAME}"
OutFile "private-browser-setup.exe"

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "install"
    SetOutPath $INSTDIR
    File /r "..\dist\private-browser\*.*"

    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\private-browser.exe"
    CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\private-browser.exe"

    WriteRegStr HKCU "Software\Classes\.pbprof" "" "PrivateBrowser.Profile"
    WriteRegStr HKCU "Software\Classes\PrivateBrowser.Profile" "" "Private Browser Profile"
    WriteRegStr HKCU "Software\Classes\PrivateBrowser.Profile\DefaultIcon" "" "$INSTDIR\private-browser.exe,0"
    WriteRegStr HKCU "Software\Classes\PrivateBrowser.Profile\shell\open\command" "" '"$INSTDIR\private-browser.exe" "%1"'

    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayName" "${APPNAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayVersion" "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "Publisher" "${COMPANYNAME}"

    WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "uninstall"
    Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
    RMDir "$SMPROGRAMS\${APPNAME}"
    Delete "$DESKTOP\${APPNAME}.lnk"
    DeleteRegKey HKCU "Software\Classes\.pbprof"
    DeleteRegKey HKCU "Software\Classes\PrivateBrowser.Profile"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"

    ; Note: %APPDATA%\private-browser\ (user data) is preserved by default.
    ; Uncomment next line to also remove user data:
    ; RMDir /r "$APPDATA\private-browser"

    RMDir /r "$INSTDIR"
SectionEnd
