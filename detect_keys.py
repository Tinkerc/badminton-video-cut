#!/usr/bin/env python3
"""
Simple key detector for finding arrow key codes on macOS.
Run this script and press arrow keys to see their values.
"""

import cv2
import numpy as np

def main():
    # Create a blank window
    window_name = "Key Detector"
    cv2.namedWindow(window_name)

    # Create a blank image
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.imshow(window_name, img)

    print("=" * 50)
    print("Key Detector - Press keys to see their codes")
    print("=" * 50)
    print()
    print("Instructions:")
    print("  - Click on the window first")
    print("  - Press arrow keys and note the values")
    print("  - Press ESC or Q to quit")
    print()
    print("Press a key...")

    last_keys = []

    while True:
        # Display current info
        display = img.copy()

        if last_keys:
            y = 50
            for key_info in last_keys[-10:]:  # Show last 10 keys
                cv2.putText(display, key_info,
                           (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                y += 35

        cv2.putText(display, "Press keys to detect - ESC or Q to quit",
                   (20, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow(window_name, display)

        key = cv2.waitKey(0) & 0xFF

        if key == 27:  # ESC
            # Check if it's an arrow key sequence
            key1 = cv2.waitKey(1) & 0xFF
            if key1 != 255:
                key2 = cv2.waitKey(1) & 0xFF
                if key2 != 255:
                    info = f"ESC sequence: {key} -> {key1} -> {key2}"
                    last_keys.append(info)
                    print(f"  {info}")
                else:
                    info = f"ESC + {key1}"
                    last_keys.append(info)
                    print(f"  {info}")
            else:
                print("ESC (quit)")
                break

        elif key == ord('q') or key == ord('Q'):
            print("Q (quit)")
            break

        else:
            # Single key press
            key_name = chr(key) if 32 <= key <= 126 else f"code_{key}"
            info = f"Key: {key} ({key_name})"
            last_keys.append(info)
            print(f"  {info}")

    cv2.destroyAllWindows()
    print()
    print("=" * 50)
    print("Key codes detected - copy these to mark_rallies.py")
    print("=" * 50)


if __name__ == "__main__":
    main()
