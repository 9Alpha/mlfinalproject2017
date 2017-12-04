#include <iostream>
#include <windows.h>
#include <TlHelp32.h> 
#include <Tchar.h>
#include "luft_util.h"

#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib") //this is the screen cap library for windows

using namespace std; 

#define _LUFTUTIL_H_ //from .h file

extern "C" { //means it's good for any version of c

    HWND WINDOW; //handle to the Luftrausers window
    HANDLE PROCESS; //handle to the Luftrausers process

    INPUT keybrd; //struct for sending keystrokes
    WORD FIRE_KEY = 0x58; //key codes for X,
    WORD LEFT_KEY = 0x41; //A
    WORD UP_KEY = 0x57; //W
    WORD RIGHT_KEY = 0x44; //D

    int MAX_WIDTH; //image w,h
    int MAX_HEIGHT;
    RECT rect; //rect for finding w,h

    DWORD PID = 0; //process id
    int STATIC_OFFSET = 0x6aca90; //offset from Luftrausers base mem address
    int SCORE_OFFSET = 0x138; //offset from static to score
    int MULT_OFFSET = 0x128; //offset from static to mult

    BYTE *BASE_ADDR = 0; //pointer to base addr

    int PIX_DEPTH = 4; //4 becuase Luftrausers uses RGBA coloring

    BYTE *NDATA; //array to hold processed pixel values

    void init() { //init function
        WINDOW = FindWindowA(0, _T("LUFTRAUSERS")); //get window handle
        if(WINDOW == 0 ){ 
            printf("Window not found!\n"); 
            exit(1);
        } 

        GetWindowRect(WINDOW, &rect); //get image data
        MAX_WIDTH = rect.right - rect.left;
        MAX_HEIGHT = rect.bottom - rect.top;
	    InvalidateRect(WINDOW, &rect, 0);
      
        GetWindowThreadProcessId(WINDOW, &PID); //get pid 
        PROCESS = OpenProcess(PROCESS_ALL_ACCESS, FALSE, PID); //get process handle
        if(PROCESS == 0 ){ 
            printf("Process not found!\n"); 
            exit(1);
        } 
        HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, PID); //get process snapshot
        MODULEENTRY32 ModuleEntry32 = {0}; 
        ModuleEntry32.dwSize = sizeof(MODULEENTRY32); 
        Module32First(hSnapshot, &ModuleEntry32);

        BASE_ADDR = ModuleEntry32.modBaseAddr; //find base addr from snapshot

        CloseHandle(hSnapshot); //free snapshot

        keybrd.type = INPUT_KEYBOARD; //set up keyboard interface
        keybrd.ki.time = 0;
        keybrd.ki.dwExtraInfo = 0;
    }

    int getPLen() { //return len of full pixel array
        return MAX_HEIGHT * MAX_WIDTH * PIX_DEPTH;
    }

    int getH() { //return image height
        return MAX_HEIGHT;
    }

    int getW() { //return image height
        return MAX_WIDTH;
    }

    BYTE *getPix(int shrink) { //get pixels from Luftrausers screen
        HDC dc = GetDC(WINDOW); //get dc object
        HDC dcTmp = CreateCompatibleDC(dc); //not sure what this line does
        

        int iBpi= GetDeviceCaps(dcTmp, BITSPIXEL); //get pixel depth, I hardcoded in a 4 but really I shouldn't have
        BITMAPINFO bitmap;
        bitmap.bmiHeader.biSize = sizeof(BITMAPINFOHEADER); //give the bitmap the specs of our image
        bitmap.bmiHeader.biWidth = MAX_WIDTH;
        bitmap.bmiHeader.biHeight = -MAX_HEIGHT;
        bitmap.bmiHeader.biPlanes = 1;
        bitmap.bmiHeader.biBitCount  = iBpi;
        bitmap.bmiHeader.biCompression = BI_RGB;


        BYTE *data = NULL;
        HBITMAP hBitmap = CreateDIBSection(dcTmp, &bitmap, DIB_RGB_COLORS, (void**)&data, NULL, NULL); //set up pixel capture
        HGDIOBJ pbitmap = SelectObject(dcTmp, hBitmap);
        BitBlt(dcTmp, 0, 0, MAX_WIDTH, MAX_HEIGHT, dc , 0, 0, SRCCOPY); //get pixel data
        if (data == NULL) {
            printf("Get Pixels Error: %d\n", GetLastError());
            exit(1);
        }
  
        int nw = MAX_WIDTH/shrink;
        int nh = MAX_HEIGHT/shrink;
        NDATA = new BYTE[nw*nh]; //set up new pixel array
        int g = 0;
        for (int i = 0; i < MAX_WIDTH*MAX_HEIGHT*PIX_DEPTH/shrink; i += PIX_DEPTH) { //convert RGBA values to grayscale, and limit length to nw*nh
            if (g >= nw*nh) {
                break;
            }
            NDATA[g] = 0.3*data[i*shrink] + 0.59*data[i*shrink+1] + 0.11*data[i*shrink+2];
            g++;
            if ((i/PIX_DEPTH) % MAX_WIDTH == 0) {
                i += MAX_WIDTH * PIX_DEPTH * (shrink - 1);
            }
        }
	    InvalidateRect(WINDOW, &rect, 1);
      	ReleaseDC(WINDOW, dc); //free dc
        SelectObject(dcTmp, pbitmap);
        DeleteDC(dcTmp);
        DeleteObject(pbitmap);
        DeleteObject(hBitmap);
        return NDATA;
    }

    void readGameMem(int *rtrn) { //get score and mult variables
        int score;
        int mult;
        int mem; 
        SIZE_T numBytesRead; 
        if (!ReadProcessMemory(PROCESS, (LPCVOID)(BASE_ADDR+STATIC_OFFSET), &mem, sizeof(int), &numBytesRead)) { //first get offset address
            printf("Getting mem, error %d\n", GetLastError());
            exit(1);
        } 
        if (!ReadProcessMemory(PROCESS, (LPCVOID)(mem+SCORE_OFFSET), &score, sizeof(int), &numBytesRead)) { //read score
            printf("Getting mem, error %d\n", GetLastError());
            exit(1);
        }
        if (!ReadProcessMemory(PROCESS, (LPCVOID)(mem+MULT_OFFSET), &mult, sizeof(int), &numBytesRead)) { // read mult
            printf("Getting mem, error %d\n", GetLastError());
            exit(1);
        }

        rtrn[0] = score; //no nead to return, just pass the values to rtrn
        rtrn[1] = mult;
    }

    void sendKey(int action) { //send key
        if (action < 4) { //if <4, it's a press
            keybrd.ki.dwFlags = KEYEVENTF_SCANCODE;
            if (action == 0) {
                keybrd.ki.wScan = MapVirtualKey(FIRE_KEY, MAPVK_VK_TO_VSC); //use a scancode not a raw value because Luftrauses doesn't see the keyboard the same way cpp does I guess
                SendInput(1, &keybrd, sizeof(INPUT));
            } else if (action == 1) {
                keybrd.ki.wScan = MapVirtualKey(LEFT_KEY, MAPVK_VK_TO_VSC);
                SendInput(1, &keybrd, sizeof(INPUT));
            } else if (action == 2) {
                keybrd.ki.wScan = MapVirtualKey(UP_KEY, MAPVK_VK_TO_VSC);
                SendInput(1, &keybrd, sizeof(INPUT));
            } else if (action == 3) {
                keybrd.ki.wScan = MapVirtualKey(RIGHT_KEY, MAPVK_VK_TO_VSC);
                SendInput(1, &keybrd, sizeof(INPUT));
            }
        } else { //if >=4, it's a release
            keybrd.ki.dwFlags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP;
            if (action == 4) {
                keybrd.ki.wScan = MapVirtualKey(FIRE_KEY, MAPVK_VK_TO_VSC);
                SendInput(1, &keybrd, sizeof(INPUT));
            } else if (action == 5) {
                keybrd.ki.wScan = MapVirtualKey(LEFT_KEY, MAPVK_VK_TO_VSC);
                SendInput(1, &keybrd, sizeof(INPUT));
            } else if (action == 6) {
                keybrd.ki.wScan = MapVirtualKey(UP_KEY, MAPVK_VK_TO_VSC);
                SendInput(1, &keybrd, sizeof(INPUT));
            } else if (action == 7) {
                keybrd.ki.wScan = MapVirtualKey(RIGHT_KEY, MAPVK_VK_TO_VSC);
                SendInput(1, &keybrd, sizeof(INPUT));
            }
        }
        //printf("Sent key %d with error %d\n", action, GetLastError());
    }

    void closePMem() { //frees some memory
        CloseHandle(PROCESS); 
        delete [] NDATA;
    }

    int main() { //for testing purposes
        init();
        int *score = new int[2];
        for (int i = 0; i < 1000; i++) {
            readGameMem(score);
            getPix(2);
        }
        delete [] score;
        closePMem();
        exit(0);
    }

}