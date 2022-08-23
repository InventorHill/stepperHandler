#!/usr/bin/python3
#
# Connect the GPIO pins to PUL+, DIR+ and the emergency stop button
#
# Connect ground to PUL-, DIR- and the other terminal of the emergency stop button

import tkinter as tk
from tkinter import filedialog as fd
from time import sleep
import sys
from os import path
import re
import RPi.GPIO as GPIO
import threading
import subprocess
from requests import get

PUL = [ 0, 0, 0 ]  # PUL pins
DIR = [ 0, 0, 0 ]  # Controller Direction Pin (High for Controller default /
                   # LOW to Force a Direction Change).
delay = [0.0, 0.0, 0.0] # Delay between PUL pulses - effectively sets the motor
                        # rotation speed.
EMER = 0 # Emergency stop pin
dirs = [True, True, True] # True for clockwise, False for anticlockwise
operating = [False, False, False] # Allows each motor to be turned on or off
                                  # independently
rpm_0 = [False, False, False] # True if RPM set to 0 in GUI; prevents divide by 0 
                              # error
gpio_handler = None
app = None

version = "1.0.0"

url_main = ("https://raw.githubusercontent.com/InventorHill/stepperHandler"
                "/main/stepperHandler/")

# Class to interact with the user
class MainWindow(tk.Tk):
    started = False

    letter_pressed = 0 # Number of letters currently being pressed

    titles = [ "main", "settings", "error"]
    window_name = "main" # Title of window currently shown
    main_window = True # When the OK button is pressed on the error window,
                       # this tells the program whether to revert to the settings 
                       # or to the main window

    widgets = {
        "main" : None,
        "settings" : None,
        "errors" : None
    } # Allows iteration through widgets

    tp_mtr_run = None
    md_mtr_run = None
    bt_mtr_run = None
    cw_var = None
    bcm_pins = None

    entries = {
        "main" : [],
        "settings" : []
    } # Entry widget names

    errors = {
         "NaN" : "THE VALUE ENTERED WAS NOT A NUMBER",
         "NaI" : "THE VALUE ENTERED WAS NOT AN INTEGER",
         "Neg" : "THE VALUE ENTERED WAS NEGATIVE",
         "NaP" : "THE VALUE ENTERED WAS NOT A VALID PIN NUMBER",
         "NaL" : "THE VALUE ENTERED WAS NOT A LETTER",
         "AlU" : "THE VALUE ENTERED HAS ALREADY BEEN USED",
         "Unc" : "NOT ALL FIELDS HAVE BEEN FILLED IN",
         "Set" : "ERROR IN SETTINGS FILE\nNO DATA HAS BEEN ENTERED INTO FIELDS"
    }

    pins = [] # Pins to use with motors and emergency stop
    letters = [] # Entry widgets storing increment/decrement letters

    error = ""

    settings_filepath = ""

    settings_filename = None

    settings = {
        "top": {
            "rpm" : ["tp_rpm_ent", "main", "", "NaN", "The motor's actual RPM"],
            "increment" : ["tp_inc_ent", "main", "", "NaL", ("The letter used to "
                "increment the RPM of the motor")],
            "decrement" : ["tp_dec_ent", "main", "", "NaL", ("The letter used to "
                "decrement the RPM of the motor")],
            "in_decrement_value" : ["tp_inc_val_ent", "main", "", "NaN", ("The "
                "value by which the motor's RPM is incremented or decremented")],
            "direction" : ["nul", "main", True, "NaB", ("A binary value (1 or 0) "
                "denoting the direction of the motor's rotation")],
            "pulses_revolution" : ["tp_spr_ent", "settings", "", "NaI", ("The "
                "number of pulses per revolution set using the dip switches on the "
                "controller")],
            "pul_pin" : ["tp_pul_ent", "settings", "", "NaP", ("The physical "
                "location of the PUL pin (odd on the left-hand side, even on the "
                "right)")],
            "dir_pin" : ["tp_dir_ent", "settings", "", "NaP", ("The physical "
                "location of the DIR pin (odd on the left-hand side, even on the "
                "right)")]
        },
        "middle" : {
            "rpm" : ["md_rpm_ent", "main", "", "NaN", ""],
            "increment" : ["md_inc_ent", "main", "", "NaL", ""],
            "decrement" : ["md_dec_ent", "main", "", "NaL", ""],
            "in_decrement_value" : ["md_inc_val_ent", "main", "", "NaN", ""],
            "direction" : ["nul", "main", True, "NaB", ""],
            "pulses_revolution" : ["md_spr_ent", "settings", "", "NaI", ""],
            "pul_pin" : ["md_pul_ent", "settings", "", "NaP", ""],
            "dir_pin" : ["md_dir_ent", "settings", "", "NaP", ""]
        },
        "bottom" : {
            "rpm" : ["bt_rpm_ent", "main", "", "NaN", ""],
            "increment" : ["bt_inc_ent", "main", "", "NaL", ""],
            "decrement" : ["bt_dec_ent", "main", "", "NaL", ""],
            "in_decrement_value" : ["bt_inc_val_ent", "main", "", "NaN", ""],
            "direction" : ["cw_var", "main", True, "NaB", ""],
            "wrong_direction" : ["nul", "main", False, "NaB", ("Set this to 1 if "
            "the motor is turning in the opposite direction to that which was set "
            "in the GUI; otherwise, leave it at 0")],
            "pulses_revolution" : ["bt_spr_ent", "settings", "", "NaI", ""],
            "pul_pin" : ["bt_pul_ent", "settings", "", "NaP", ""],
            "dir_pin" : ["bt_dir_ent", "settings", "", "NaP", ""]
        },
        "all" : {
            "increment" : ["al_inc_ent", "main", "", "NaL", ""],
            "decrement" : ["al_dec_ent", "main", "", "NaL", ""],
            "percentage" : ["al_inc_val_ent", "main", "", "NaN", ("The percentage "
            "by which to increment or decrement all motors")]
        },
        "emergency" : {
            "stop_pin" : ["emer_stp_ent", "settings", "", "NaP", ("The physical "
            "location of the emergency stop pin (odd on the left-hand side, even "
            "on the right)")]
        }
    } # Widget name, window in which it will be found, value, error if value
      # incorrect, comment in settings file. Default comments are provided here,
      # but they can be changed by editing the settings file

    disable_widgets = [
        "tp_rpm_ent",
        "tp_inc_ent",
        "tp_dec_ent",
        "md_rpm_ent",
        "md_inc_ent",
        "md_dec_ent",
        "bt_rpm_ent",
        "bt_inc_ent",
        "bt_dec_ent",
        "bt_acw_rdo",
        "bt_cw_rdo",
        "al_inc_ent",
        "al_dec_ent",
        "sett_btn"
    ] # Widgets to be disabled when motors have been started

    # Called when the class is created
    def __init__(self):
        global widgets
        global tp_mtr_run
        global md_mtr_run
        global bt_mtr_run
        global pins
        global letters
        global entries
        global settings
        global cw_var
        global bcm_pins
        global version
        global settings_filepath
        global settings_filename

        super().__init__()

        # Get GPIO pins
        self.bcm_pins = str(subprocess.run("pinout", stdout=subprocess.PIPE))

        self.settings_filename = tk.StringVar()
        self.settings_filename.set("stepperSettings.cfg")
        self.settings_filepath = path.join(sys.path[0], self.settings_filename.get())

        # Specify all necessary key bindings
        self.bind_all("<KeyPress>", self.keypress)
        self.bind_all("<KeyRelease>", self.keyrelease)
        self.bind_all("<Alt-s>", lambda event: self.specialPress("alt", "s"))
        self.bind_all("<Shift-s>", lambda event: self.specialPress("shift", "s"))
        self.bind_all("<Control-s>", lambda event: self.specialPress("ctrl", "s"))
        self.bind_all("<Control-c>", lambda event: self.specialPress("ctrl", "c"))
        self.bind_all("<Control-x>", lambda event: self.onClosing())
        self.bind_all("<Alt-S>", lambda event: self.specialPress("alt", "s"))
        self.bind_all("<Shift-S>", lambda event: self.specialPress("shift", "s"))
        self.bind_all("<Control-S>", lambda event: self.specialPress("ctrl", "s"))
        self.bind_all("<Control-C>", lambda event: self.specialPress("ctrl", "c"))
        self.bind_all("<Control-X>", lambda event: self.onClosing())
        self.bind_all("<Return>", lambda event: self.specialPress("return", ""))

        self.tp_mtr_run = tk.BooleanVar(self.master, False)
        self.md_mtr_run = tk.BooleanVar(self.master, False)
        self.bt_mtr_run = tk.BooleanVar(self.master, False)
        self.cw_var = tk.BooleanVar(self.master, True)

        vnan = (self.register(self.validateNan), "%P")
        vnai = (self.register(self.validateNai), "%P")
        vnal = (self.register(self.validateAlu), "%P", False)
        vpin = (self.register(self.validateAlu), "%P", True)

        self.getVersion()

        # Define all widgets
        self.widgets["main"] = {
            "vers_lbl" : tk.Label(self.master, text="v{0}".format(version)),
            "sett_btn" : tk.Button(self.master, text="SETTINGS (ALT + S)",
                command=(self.register(self.createWindow), "settings")),

            "file_lbl" : tk.Label(self.master, textvariable=self.settings_filename),

            "file_btn" : tk.Button(self.master, text="CHANGE SETTINGS FILE",
                command=self.selectSettingsFile),

            "tp_mtr_lbl" : tk.Label(self.master, text="TOP MOTOR:"),
            "tp_rpm_lbl" : tk.Label(self.master, text="RPM"),
            "tp_inc_lbl" : tk.Label(self.master, text="INCREMENT\nRPM LETTER"),
            "tp_inc_val_lbl" : tk.Label(self.master, text="IN/DECREMENT\nVALUE"),
            "tp_dec_lbl" : tk.Label(self.master, text="DECREMENT\nRPM LETTER"),
            "tp_run_lbl" : tk.Label(self.master, text="RUNNING"),
            "tp_run_chk" : tk.Checkbutton(self.master, variable=self.tp_mtr_run,
                onvalue=True, offvalue=False, command=self.checkPressed),
            "tp_rpm_ent" : tk.Entry(self.master, width=5,
                validate="focusout", validatecommand=vnan,
                invalidcommand=(self.register(self.invalid), "main", "tp_rpm_ent")),
            "tp_inc_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vnal,
                invalidcommand=(self.register(self.invalid), "main", "tp_inc_ent")),
            "tp_inc_val_ent" : tk.Entry(self.master, width=3,
                validate="focusout", validatecommand=vnan,
                invalidcommand=(self.register(self.invalid), "main",
                "tp_inc_val_ent")),
            "tp_dec_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vnal, 
                invalidcommand=(self.register(self.invalid), "main", "tp_dec_ent")),

            "md_mtr_lbl" : tk.Label(self.master, text="MIDDLE MOTOR:"),
            "md_rpm_lbl" : tk.Label(self.master, text="RPM"),
            "md_inc_lbl" : tk.Label(self.master, text="INCREMENT\nRPM LETTER"),
            "md_inc_val_lbl" : tk.Label(self.master, text="IN/DECREMENT\nVALUE"),
            "md_dec_lbl" : tk.Label(self.master, text="DECREMENT\nRPM LETTER"),
            "md_run_lbl" : tk.Label(self.master, text="RUNNING"),
            "md_run_chk" : tk.Checkbutton(self.master, variable=self.md_mtr_run,
                onvalue=True, offvalue=False, command=self.checkPressed),
            "md_rpm_ent" : tk.Entry(self.master, width=5,
                validate="focusout", validatecommand=vnan,
                invalidcommand=(self.register(self.invalid), "main", "md_rpm_ent")),
            "md_inc_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vnal,
                invalidcommand=(self.register(self.invalid), "main", "md_inc_ent")),
            "md_inc_val_ent" : tk.Entry(self.master, width=3,
                validate="focusout", validatecommand=vnan,
                invalidcommand=(self.register(self.invalid), "main",
                "md_inc_val_ent")),
            "md_dec_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vnal,
                invalidcommand=(self.register(self.invalid), "main", "md_dec_ent")),

            "bt_mtr_lbl" : tk.Label(self.master, text="BOTTOM MOTOR:"),
            "bt_rpm_lbl" : tk.Label(self.master, text="RPM"),
            "bt_inc_lbl" : tk.Label(self.master, text="INCREMENT\nRPM LETTER"),
            "bt_inc_val_lbl" : tk.Label(self.master, text="IN/DECREMENT\nVALUE"),
            "bt_dec_lbl" : tk.Label(self.master, text="DECREMENT\nRPM LETTER"),
            "bt_run_lbl" : tk.Label(self.master, text="RUNNING"),
            "bt_run_chk" : tk.Checkbutton(self.master, variable=self.bt_mtr_run,
                onvalue=True, offvalue=False, command=self.checkPressed),
            "bt_rpm_ent" : tk.Entry(self.master, width=5,
                validate="focusout", validatecommand=vnan,
                invalidcommand=(self.register(self.invalid), "main", "bt_rpm_ent")),
            "bt_inc_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vnal,
                invalidcommand=(self.register(self.invalid), "main", "bt_inc_ent")),
            "bt_inc_val_ent" : tk.Entry(self.master, width=3,
                validate="focusout", validatecommand=vnan,
                invalidcommand=(self.register(self.invalid), "main",
                "bt_inc_val_ent")),
            "bt_dec_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vnal,
                invalidcommand=(self.register(self.invalid), "main", "bt_dec_ent")),

            "bt_acw_lbl" : tk.Label(self.master, text="COUNTER-\nCLOCKWISE"),
            "bt_cw_lbl" : tk.Label(self.master, text="CLOCKWISE"),
            "bt_acw_rdo" : tk.Radiobutton(self.master, variable=self.cw_var,
                value=False),
            "bt_cw_rdo" : tk.Radiobutton(self.master, variable=self.cw_var,
                value=True),

            "al_mtr_lbl" : tk.Label(self.master, text="ALL MOTORS:"),
            "al_inc_lbl" : tk.Label(self.master, text=("INCREMENT\nPERCENTAGE\n"
                "LETTER")),
            "al_dec_lbl" : tk.Label(self.master, text=("DECREMENT\nPERCENTAGE\n"
                "LETTER")),
            "al_inc_val_lbl" : tk.Label(self.master, text=("IN/DECREMENT\nPERCENT"
                "AGE\nVALUE")),
            "al_inc_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vnal,
                invalidcommand=(self.register(self.invalid), "main", "al_inc_ent")),
            "al_dec_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vnal,
                invalidcommand=(self.register(self.invalid), "main", "al_dec_ent")),
            "al_inc_val_ent" : tk.Entry(self.master, width=3,
                validate="focusout", validatecommand=vnan,
                invalidcommand=(self.register(self.invalid), "main",
                "al_inc_val_ent")),

            "strt_btn" : tk.Button(self.master, text="START ALL (SHIFT + S)",
                command=self.startPressed)
        }

        self.widgets["settings"] = {
            "tp_mtr_lbl" : tk.Label(self.master, text="TOP MOTOR:"),
            "tp_spr_lbl" : tk.Label(self.master, text=("MICROSTEPS (PULSES)\n "
                "PER REVOLUTION")),
            "tp_pul_lbl" : tk.Label(self.master, text="PUL PHYSICAL\nPIN"),
            "tp_dir_lbl" : tk.Label(self.master, text="DIR PHYSICAL\nPIN"),
            "tp_spr_ent" : tk.Entry(self.master, width=5,
                validate="focusout", validatecommand=vnai,
                invalidcommand=(self.register(self.invalid), "settings",
                "tp_spr_ent")),
            "tp_pul_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vpin,
                invalidcommand=(self.register(self.invalid), "settings",
                "tp_pul_ent")),
            "tp_dir_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vpin,
                invalidcommand=(self.register(self.invalid), "settings",
                "tp_dir_ent")),

            "md_mtr_lbl" : tk.Label(self.master, text="MIDDLE MOTOR:"),
            "md_spr_lbl" : tk.Label(self.master, text=("MICROSTEPS (PULSES)\n "
                "PER REVOLUTION")),
            "md_pul_lbl" : tk.Label(self.master, text="PUL PHYSICAL\nPIN"),
            "md_dir_lbl" : tk.Label(self.master, text="DIR PHYSICAL\nPIN"),
            "md_spr_ent" : tk.Entry(self.master, width=5,
                validate="focusout", validatecommand=vnai,
                invalidcommand=(self.register(self.invalid), "settings",
                "md_spr_ent")),
            "md_pul_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vpin,
                invalidcommand=(self.register(self.invalid), "settings",
                "md_pul_ent")),
            "md_dir_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vpin,
                invalidcommand=(self.register(self.invalid), "settings",
                "md_dir_ent")),

            "bt_mtr_lbl" : tk.Label(self.master, text="BOTTOM MOTOR:"),
            "bt_spr_lbl" : tk.Label(self.master, text=("MICROSTEPS (PULSES)\n "
                "PER REVOLUTION")),
            "bt_pul_lbl" : tk.Label(self.master, text="PUL PHYSICAL\nPIN"),
            "bt_dir_lbl" : tk.Label(self.master, text="DIR PHYSICAL\nPIN"),
            "bt_spr_ent" : tk.Entry(self.master, width=5,
                validate="focusout", validatecommand=vnai,
                invalidcommand=(self.register(self.invalid), "settings",
                "bt_spr_ent")),
            "bt_pul_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vpin,
                invalidcommand=(self.register(self.invalid), "settings",
                "bt_pul_ent")),
            "bt_dir_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vpin,
                invalidcommand=(self.register(self.invalid), "settings",
                "bt_dir_ent")),

            "emer_stp_lbl" : tk.Label(self.master, text=("EMERGENCY STOP\n"
                "PHYSICAL PIN")),
            "emer_stp_ent" : tk.Entry(self.master, width=2,
                validate="focusout", validatecommand=vpin,
                invalidcommand=(self.register(self.invalid), "settings",
                "emer_stp_ent")),

            "sv_btn" : tk.Button(self.master, text="SAVE SETTINGS (CTRL + S)",
                command=self.savePressed),
            "cncl_btn" : tk.Button(self.master, text="CANCEL (CTRL + C)",
                command=self.cancelPressed)
        }

        self.widgets["errors"] = {
            "err_lbl" : tk.Label(self.master, text=("THE VALUE ENTERED WAS NOT "
                "A NUMBER")),
            "ok_btn" : tk.Button(self.master, text="OK (ENTER)",
                command=(self.register(self.createWindow), "unknown"))
        }

        for key in self.widgets["main"]:
            if "_inc_ent" in key or "_dec_ent" in key:
                self.letters.append(key)
            if "_ent" in key:
                self.entries["main"].append(key)
        
        for key in self.widgets["settings"]:
            if (("_pul_" in key or "_dir_" in key or "emer_" in key) 
            and "_lbl" not in key and "_chk" not in key):
                self.pins.append(key)
            if "_ent" in key:
                self.entries["settings"].append(key)

        self.resizable(False, False)

        if self.readFile():
            self.createWindow(name="main")

        # When the X in top right corner is pressed, the following procedure
        # will be called
        self.protocol("WM_DELETE_WINDOW", self.onClosing)

    # Defined keypress with modifier
    def specialPress(self, modifier, letter):
        global window_name
        global started

        if self.window_name == "main":
            if letter == "s":
                if modifier == "alt" and not self.started:
                    self.createWindow("settings")
                elif modifier == "shift":
                    focussed_widget = self.focus_get()
                    if isinstance(focussed_widget, tk.Entry):
                        # Regex to remove all characters which are not numbers
                        txt = re.sub("[^0-9]", "", focussed_widget.get())
                        focussed_widget.delete(0, tk.END)
                        focussed_widget.insert(0, txt)
                    self.startPressed()
        elif self.window_name == "settings" and not self.started:
            if modifier == "ctrl":
                if letter == "s":
                    self.savePressed()
                elif letter == "c":
                    self.cancelPressed()
        else:
            if modifier == "return":
                self.createWindow("unknown")

    def selectSettingsFile(self):
        global settings_filename
        global settings_filepath

        filetypes = (("Configuration Files", "*.cfg"),)

        filepath = fd.askopenfilename(
            title="Select Settings Configuration File",
            initialdir=sys.path[0],
            filetypes=filetypes
        )

        self.settings_filepath = filepath if filepath != "" else self.settings_filepath

        self.settings_filename.set(path.basename(self.settings_filepath))

    # Called for all keypresses
    def keypress(self, e):
        global window_name
        global letter_pressed
        global started
        global operating
        global widgets

        if self.started:
            # Ensures modifier key has not been pressed
            if e.char == e.keysym:
                self.letter_pressed += 1
            else:
                return

            if self.letter_pressed == 1:
                increment_letters = [
                    self.settings["top"]["increment"][2].lower(),
                    self.settings["top"]["decrement"][2].lower(),
                    self.settings["middle"]["increment"][2].lower(),
                    self.settings["middle"]["decrement"][2].lower(),
                    self.settings["bottom"]["increment"][2].lower(),
                    self.settings["bottom"]["decrement"][2].lower(),
                    self.settings["all"]["increment"][2].lower(),
                    self.settings["all"]["decrement"][2].lower()
                ]

                if not str(e.char).isdigit():
                    focussed_widget = self.focus_get()
                    if isinstance(focussed_widget, tk.Entry):
                        txt = re.sub("[^0-9]", "", focussed_widget.get())
                        focussed_widget.delete(0, tk.END)
                        focussed_widget.insert(0, txt)

                settings_keys = list(self.settings.keys())
                for i in range(4):
                    motor = settings_keys[i]
                    widget_name = "{0}{1}_inc_val_ent".format(motor[0:1],
                        motor[2:3])
                    key_name = "in_decrement_value" if i < 3 else "percentage"
                    if self.widgets["main"][widget_name].get() == "":
                        self.widgets["main"][widget_name].delete(0, tk.END)
                        self.widgets["main"][widget_name].insert(0,
                            self.settings[motor][key_name][2])
                # Calls increment procedure if letter pressed corresponds to a set
                # increment/decrement letter
                if e.char.lower() in increment_letters:
                    index = increment_letters.index(e.char.lower())
                    motor = ("top" if index < 2 else "middle" if index < 4 
                        else "bottom" if index < 6 else "all")
                    widget_name = "{0}{1}_inc_val_ent".format(motor[0:1],
                        motor[2:3])
                    key_name = "in_decrement_value" if index < 6 else "percentage"
                    inc_dec = self.widgets["main"][widget_name].get()
                    self.settings[motor][key_name][2] = inc_dec
                    if index >= 6 or operating[int((index - (index % 2)) / 2)]:
                        self.setIncrement(motor, 
                            (1 if index % 2 == 0 else -1) * float(inc_dec))

    # Called for all times key is released
    def keyrelease(self, e):
        global letter_pressed

        # Ensures modifier key has not been pressed
        if len(e.keysym) == 1 and self.started:
            self.letter_pressed -= 0 if self.letter_pressed <= 0 else 1

    # Called whenever the program is about to close
    def onClosing(self):
        global gpio_handler
        global started

        if self.started:
            self.startPressed()

        gpio_handler.stopThreads()
        self.writeFile()
        self.destroy()

    # Called whenever the state of a checkbox is changed
    def checkPressed(self):
        global tp_mtr_run
        global md_mtr_run
        global bt_mtr_run
        global operating

        operating[0] = self.tp_mtr_run.get()
        operating[1] = self.md_mtr_run.get()
        operating[2] = self.bt_mtr_run.get()

    # Restores values set in settings to widgets in settings window when
    # cancel button pressed
    def cancelPressed(self):
        global settings
        global widgets

        for key in self.settings:
            for sub_key in self.settings[key]:
                if self.settings[key][sub_key][1] == "settings":
                    widget = self.settings[key][sub_key][0]
                    if widget != "nul" and widget != "cw_var":
                        self.widgets["settings"][widget].delete(0, tk.END)
                        self.widgets["settings"][widget].insert(0, 
                            self.settings[key][sub_key][2])
        
        self.createWindow("main")

    # Called when the user presses the key to either increment or decrement
    # a motor's RPM
    def setIncrement(self, motor_name, value):
        global settings
        global delay
        global widgets
        global operating
        global rpm_0

        motors = (["top", "middle", "bottom"] if motor_name == "all"
            else [motor_name])

        if motor_name == "all":
            for op in operating:
                if not op:
                    return
        
        for motor in motors:
            index = list(self.settings.keys()).index(motor)
            widget_name = "{0}{1}_rpm_ent".format(motor[0:1], motor[2:3])
            rpm = float(self.widgets["main"][widget_name].get())
            rpm += value if motor_name != "all" else float(rpm * value) / 100.0
            rpm = 0.0 if rpm < 0.0 else rpm

            # Removes last characters (.0) if rpm is integer; this looks nicer on
            # the GUI
            rpm_str = str(rpm)[:-2] if str(rpm)[-2:] == ".0" else str(rpm)

            self.widgets["main"][widget_name].configure(state="normal")
            self.widgets["main"][widget_name].delete(0, tk.END)
            self.widgets["main"][widget_name].insert(0, rpm_str)
            self.widgets["main"][widget_name].configure(state="disabled")

            if rpm <= 0.0:
                rpm_0[index] = True
                continue
            else:
                rpm_0[index] = False

            _delay = ((30.0 / (float(self.settings[motor]["pulses_revolution"][2])
                * rpm)))

            if _delay <= 0.0:
                rpm_0[index] = True
                continue
            else:
                rpm_0[index] = False

            delay[index] = _delay

    # Called whenever the start button OR the stop button has been pressed
    # (they are the same button, but with different text)
    def startPressed(self):
        global entries
        global widgets
        global started
        global disable_widgets
        global settings
        global PUL
        global DIR
        global delay
        global dirs
        global gpio_handler
        global rpm_0
        global EMER

        # present = True is equivalent to all entry widgets being filled in
        present = True

        if not self.started:
            for key_main in self.entries:
                for key in self.entries[key_main]:
                    present = present and self.widgets[key_main][key].get() != ""

        keys = list(self.settings.keys())

        if present:
            if self.started:
                gpio_handler.pauseThreads()
                self.started = False

                for i in range(len(PUL)):
                    widget_name = "{0}{1}_rpm_ent".format(keys[i][0:1],
                        keys[i][2:3])
                    self.widgets["main"][widget_name].configure(state="normal")
                    self.widgets["main"][widget_name].delete(0, tk.END)
                    self.widgets["main"][widget_name].insert(0,
                        self.settings[keys[i]]["rpm"][2])
                for value in self.disable_widgets:
                    self.widgets["main"][value].configure(state="normal")
                self.widgets["main"]["strt_btn"].configure(text=("START ALL "
                    "(SHIFT + S)"))
            else:
                # Placed here as self.writeFile() also updates settings variable
                self.writeFile()

                # Sets all settings read by the GPIO handler
                for i in range(len(PUL)):
                    _pul = int(self.settings[keys[i]]["pul_pin"][2])
                    _dir = int(self.settings[keys[i]]["dir_pin"][2])
                    PUL[i] = self.board_bcm(_pul)
                    DIR[i] = self.board_bcm(_dir)
                    self.setIncrement(keys[i], 0.0)

                    switch_dir = (keys[i] == "bottom"
                        and self.settings["bottom"]["wrong_direction"][2])
                    _dir = self.settings[keys[i]]["direction"][2]
                    dirs[i] = not _dir if switch_dir else _dir

                _emer = int(self.settings["emergency"]["stop_pin"][2])
                EMER = self.board_bcm(_emer)

                for value in self.disable_widgets:
                    # Prevents inadvertent modification of values whilst running
                    self.widgets["main"][value].configure(state="disabled")
                self.widgets["main"]["strt_btn"].configure(text=("STOP ALL "
                    "(SHIFT + S)"))
                gpio_handler.resumeThreads()
                self.started = True
        else:
            self.createWindow(name="errors", error="Unc")

    # Called when save button on settings window is pressed
    def savePressed(self):
        global entries
        global widgets

        # See startPressed() procedure
        present = True

        for key in self.entries["settings"]:
            present = present and self.widgets["settings"][key].get() != ""
        
        if not present:
            self.createWindow(name="errors", error="Unc")
        else:
            self.writeFile()
            self.createWindow(name="main")

    # Called whenever a new layout needs to be created, e.g. settings to main
    def createWindow(self, name, error="", motor=""):
        global widgets
        global window_name
        global titles
        global errors
        global main_window

        name = (name if name != "unknown" else "main" if self.main_window
            else "settings")

        # Hides all widgets currently being shown
        for key in self.widgets[self.window_name]:
            self.widgets[self.window_name][key].grid_forget()

        self.window_name = name
        self.title("Stepper Handler" if name == "main"
            else "Stepper Handler Settings")
        self.widgets[name][list(self.widgets[name].keys())[0]].focus_set()

        # Positions all the widgets for the main window
        if name == "main":
            self.main_window = True

            self.widgets["main"]["vers_lbl"].grid(row=0, column=0, padx=5, sticky="w")
            self.widgets["main"]["sett_btn"].grid(row=1, column=0, columnspan=4, sticky="we",
                padx=5, pady=5)
            self.widgets["main"]["file_btn"].grid(row=1, column=4, columnspan=3, sticky="we",
                padx=5, pady=5)
            self.widgets["main"]["file_lbl"].grid(row=1, column=7, columnspan=4, sticky="we",
                padx=5, pady=5)

            self.widgets["main"]["tp_mtr_lbl"].grid(row=2, column=0, padx=5, pady=5)
            self.widgets["main"]["tp_rpm_lbl"].grid(row=2, column=1, padx=5, pady=5)
            self.widgets["main"]["tp_inc_lbl"].grid(row=2, column=3, padx=5, pady=5)
            self.widgets["main"]["tp_dec_lbl"].grid(row=2, column=5, padx=5, pady=5)
            self.widgets["main"]["tp_run_lbl"].grid(row=2, column=9, padx=5, pady=5)
            self.widgets["main"]["tp_run_chk"].grid(row=2, column=10, pady=5)
            self.widgets["main"]["tp_rpm_ent"].grid(row=2, column=2, padx=5, pady=5)
            self.widgets["main"]["tp_inc_ent"].grid(row=2, column=4, padx=5, pady=5)
            self.widgets["main"]["tp_dec_ent"].grid(row=2, column=6, padx=5, pady=5)
            self.widgets["main"]["tp_inc_val_lbl"].grid(row=2, column=7, padx=5,
                pady=5)
            self.widgets["main"]["tp_inc_val_ent"].grid(row=2, column=8, padx=5,
                pady=5)

            self.widgets["main"]["md_mtr_lbl"].grid(row=3, column=0, padx=5, pady=5)
            self.widgets["main"]["md_rpm_lbl"].grid(row=3, column=1, padx=5, pady=5)
            self.widgets["main"]["md_inc_lbl"].grid(row=3, column=3, padx=5, pady=5)
            self.widgets["main"]["md_dec_lbl"].grid(row=3, column=5, padx=5, pady=5)
            self.widgets["main"]["md_run_lbl"].grid(row=3, column=9, padx=5, pady=5)
            self.widgets["main"]["md_run_chk"].grid(row=3, column=10, pady=5)
            self.widgets["main"]["md_rpm_ent"].grid(row=3, column=2, padx=5, pady=5)
            self.widgets["main"]["md_inc_ent"].grid(row=3, column=4, padx=5, pady=5)
            self.widgets["main"]["md_dec_ent"].grid(row=3, column=6, padx=5, pady=5)
            self.widgets["main"]["md_inc_val_lbl"].grid(row=3, column=7, padx=5,
                pady=5)
            self.widgets["main"]["md_inc_val_ent"].grid(row=3, column=8, padx=5,
                pady=5)

            self.widgets["main"]["bt_mtr_lbl"].grid(row=4, column=0, padx=5, pady=5)
            self.widgets["main"]["bt_rpm_lbl"].grid(row=4, column=1, padx=5, pady=5)
            self.widgets["main"]["bt_inc_lbl"].grid(row=4, column=3, padx=5, pady=5)
            self.widgets["main"]["bt_dec_lbl"].grid(row=4, column=5, padx=5, pady=5)
            self.widgets["main"]["bt_run_lbl"].grid(row=4, column=9, padx=5, pady=5)
            self.widgets["main"]["bt_run_chk"].grid(row=4, column=10, pady=5)
            self.widgets["main"]["bt_rpm_ent"].grid(row=4, column=2, padx=5, pady=5)
            self.widgets["main"]["bt_inc_ent"].grid(row=4, column=4, padx=5, pady=5)
            self.widgets["main"]["bt_dec_ent"].grid(row=4, column=6, padx=5, pady=5)
            self.widgets["main"]["bt_inc_val_lbl"].grid(row=4, column=7, padx=5,
                pady=5)
            self.widgets["main"]["bt_inc_val_ent"].grid(row=4, column=8, padx=5,
                pady=5)

            self.widgets["main"]["bt_cw_lbl"].grid(row=5, column=5, padx=5)
            self.widgets["main"]["bt_acw_lbl"].grid(row=5, column=7, padx=5)
            self.widgets["main"]["bt_cw_rdo"].grid(row=5, column=6, padx=5)
            self.widgets["main"]["bt_acw_rdo"].grid(row=5, column=8, padx=5)

            self.widgets["main"]["al_mtr_lbl"].grid(row=6, column=0, padx=5, pady=5)
            self.widgets["main"]["al_inc_lbl"].grid(row=6, column=3, padx=5, pady=5)
            self.widgets["main"]["al_dec_lbl"].grid(row=6, column=5, padx=5, pady=5)
            self.widgets["main"]["al_inc_val_lbl"].grid(row=6, column=7, padx=5,
                pady=5)
            self.widgets["main"]["al_inc_ent"].grid(row=6, column=4, padx=5, pady=5)
            self.widgets["main"]["al_dec_ent"].grid(row=6, column=6, padx=5, pady=5)
            self.widgets["main"]["al_inc_val_ent"].grid(row=6, column=8, padx=5,
                pady=5)

            self.widgets["main"]["strt_btn"].grid(row=7, column=1, columnspan=7,
                sticky="we", pady=5)

        # Positions all the widgets for the settings window
        elif name == "settings":
            self.main_window = False

            self.widgets["settings"]["tp_mtr_lbl"].grid(row=0, column=0, padx=5)
            self.widgets["settings"]["tp_spr_lbl"].grid(row=0, column=1, padx=5)
            self.widgets["settings"]["tp_pul_lbl"].grid(row=0, column=3, padx=5,
                pady=5)
            self.widgets["settings"]["tp_dir_lbl"].grid(row=0, column=5, padx=5,
                pady=5)
            self.widgets["settings"]["tp_spr_ent"].grid(row=0, column=2, padx=5)
            self.widgets["settings"]["tp_pul_ent"].grid(row=0, column=4, padx=5,
                pady=5)
            self.widgets["settings"]["tp_dir_ent"].grid(row=0, column=6, padx=5,
                pady=5)

            self.widgets["settings"]["md_mtr_lbl"].grid(row=1, column=0, padx=5)
            self.widgets["settings"]["md_spr_lbl"].grid(row=1, column=1, padx=5)
            self.widgets["settings"]["md_pul_lbl"].grid(row=1, column=3, padx=5,
                pady=5)
            self.widgets["settings"]["md_dir_lbl"].grid(row=1, column=5, padx=5,
                pady=5)
            self.widgets["settings"]["md_spr_ent"].grid(row=1, column=2, padx=5)
            self.widgets["settings"]["md_pul_ent"].grid(row=1, column=4, padx=5,
                pady=5)
            self.widgets["settings"]["md_dir_ent"].grid(row=1, column=6, padx=5,
                pady=5)

            self.widgets["settings"]["bt_mtr_lbl"].grid(row=2, column=0, padx=5)
            self.widgets["settings"]["bt_spr_lbl"].grid(row=2, column=1, padx=5)
            self.widgets["settings"]["bt_pul_lbl"].grid(row=2, column=3, padx=5,
                pady=5)
            self.widgets["settings"]["bt_dir_lbl"].grid(row=2, column=5, padx=5,
                pady=5)
            self.widgets["settings"]["bt_spr_ent"].grid(row=2, column=2, padx=5)
            self.widgets["settings"]["bt_pul_ent"].grid(row=2, column=4, padx=5,
                pady=5)
            self.widgets["settings"]["bt_dir_ent"].grid(row=2, column=6, padx=5,
                pady=5)

            self.widgets["settings"]["emer_stp_lbl"].grid(row=3, column=3, padx=5,
                pady=5)
            self.widgets["settings"]["emer_stp_ent"].grid(row=3, column=4, padx=5,
                pady=5)

            self.widgets["settings"]["sv_btn"].grid(row=4, column=0, columnspan=3,
                padx=5, pady=5, sticky="we")
            self.widgets["settings"]["cncl_btn"].grid(row=4, column=3,
                columnspan=4, padx=5, pady=5, sticky="we")

        elif name == "errors":
            self.widgets["errors"]["err_lbl"].configure(text=self.errors[error])
            self.widgets["errors"]["err_lbl"].grid(row=0, column=0, columnspan=3,
                padx=5, pady=5)
            self.widgets["errors"]["ok_btn"].grid(row=1, column=1, padx=5, pady=5)

    # Check if data is not a number (can be a float)
    def validateNan(self, inStr):
        global error

        # Improves user experience
        if inStr == "":
            return True

        try:
            float(inStr)
            return self.validateNeg(inStr)
        except:
            self.error = "NaN"
            return False

    # Check if data is not an integer (cannot be a float)
    def validateNai(self, inStr):
        global error

        if inStr == "":
            return True

        try:
            int(inStr)
            return self.validateNeg(inStr)
        except:
            self.error = "NaI"
            return False

    # Check if data is not a valid pin value
    def validateNap(self, inStr):
        global error

        if self.validateNai(inStr):
            if int(inStr) <= 40 and int(inStr) > 0 and self.board_bcm(int(inStr),
            returnPin=False):
                return True
            else:
                self.error = "NaP"
                return False
        else:
            return False

    # Check if data is not a letter
    def validateNal(self, inStr):
        global errors

        if inStr == "":
            return True

        if inStr.isalpha() and len(inStr) == 1:
            return True
        else:
            self.error = "NaL"
            return False

    # Check if data is negative
    def validateNeg(self, inStr):
        global error

        if float(inStr) >= 0:
            return True
        else:
            self.error = "Neg"
            return False

    # Check if data has already been used in another field
    def validateAlu(self, inStr, pin):
        global widgets
        global letters
        global pins
        global error
        global settings

        in_widgets = 0

        if inStr == "":
            return True

        # pin tells the program if it needs to test if the same pin or the
        # same letter has been entered twice
        if pin == "True": # Testing showed that, for some reason,
                          # pin was received as a string
            if self.validateNap(inStr):
                for gpio in self.pins:
                    in_widgets += (1 if inStr ==
                        self.widgets["settings"][gpio].get() else 0)
            else:
                return False
        else:
            if self.validateNal(inStr):
                for letter in self.letters:
                    in_widgets += (1 if inStr ==
                        self.widgets["main"][letter].get() else 0)
            else:
                return False
        
        if in_widgets <= 1:
            return True
        else:
            self.error = "AlU"
            return False

    # Called when the data entered into the field is not valid
    def invalid(self, caller_window, caller_name):
        global widgets
        global error

        self.widgets[caller_window][caller_name].delete(0, tk.END)
        self.createWindow(name="errors", error=self.error)
        self.error = ""

    def getVersion(self):
        global version

        vers_path = path.join(sys.path[0], "version.cfg")

        if path.exists(vers_path):
            vers = open(vers_path, "r")
            version = vers.read()
            vers.close()

    # Reads the settings file into the settings variable and
    # updates the widgets
    def readFile(self):
        global settings
        global widgets
        global error
        global cw_var
        global settings_filepath

        old_settings = self.settings
        # The settings file must be in the same directory as this script
        cfg_path = path.join(sys.path[0], self.settings_filepath)

        try:
            if path.exists(cfg_path):
                cfg = open(cfg_path, "r")
                # Splits file data into top, middle, bottom and emergency
                contents = re.split("\[|\]", cfg.read())
                cfg.close()
                keys = contents[1::2] # top, middle, bottom and emergency
                values = contents[::2]
                values = list(filter(lambda l: l != "", values)) # Removes empty
                                                                 # string from list

                for i in range(len(keys)):
                    split_values = list(filter(lambda l: l != "",
                        values[i].split("\n")))
                    for j in range(len(split_values)):
                        comment_split = split_values[j].split("//")
                        key_value = comment_split[0].split("=") # [0] = key,
                                                                # [1] = value
                        cur_key = key_value[0].strip()
                        settings_keys_list = list(self.settings[keys[i]].keys())
                        if key_value[0].strip() in settings_keys_list:
                            # Set comment in settings
                            self.settings[keys[i]][cur_key][4] = (comment_split[1]
                                if len(comment_split) == 2 else "")
                            value = key_value[1].strip()
                            err_code = self.settings[keys[i]][cur_key][3]

                            if err_code == "NaN":
                                valid = self.validateNan(value)
                            elif err_code == "NaL":
                                valid = self.validateAlu(value, "False")
                            elif err_code == "NaB":
                                valid = value == "0" or value == "1"
                            elif err_code == "NaI":
                                valid = self.validateNai(value)
                            elif err_code == "NaP":
                                valid = self.validateAlu(value, "True")
                            else:
                                raise ValueError("Unknown Error Code")

                            # This prevents any possible issues if invalid()
                            # is called without error being changed
                            self.error = ""

                            if not valid:
                                raise ValueError("{0}: Invalid Data {1}"
                                    .format(err_code, value))

                            if err_code == "NaB":
                                bool_value = self.settings[keys[i]][cur_key][2]
                                self.settings[keys[i]][cur_key][2] = (value == "1"
                                    or value == "" and bool_value)
                            else:
                                self.settings[keys[i]][cur_key][2] = ("" if
                                    value == None else value)

                for key in self.settings:
                    for sub_key in self.settings[key]:
                        entry = self.settings[key][sub_key][0]
                        window = self.settings[key][sub_key][1]
                        value = self.settings[key][sub_key][2]

                        if entry != "nul" and entry != "cw_var":
                            self.widgets[window][entry].insert(0, value)
                        if entry == "cw_var":
                            self.cw_var.set(value)

        except:
            self.settings = old_settings
            self.createWindow(name="errors", error="Set")
            return False

        return True

    # Writes to the settings file from the settings variable and
    # updates the settings variable
    def writeFile(self):
        global settings
        global widgets
        global cw_var
        global settings_filepath

        lines = []

        for key in self.settings:
            lines.append("[{0}]".format(key))

            for sub_key in self.settings[key]:
                setting = self.settings[key][sub_key]
                if setting[0] == "nul":
                    value = setting[2]
                elif setting[0] == "cw_var":
                    value = self.cw_var.get()
                    self.settings[key][sub_key][2] = value
                else:
                    value = self.widgets[setting[1]][setting[0]].get()
                    self.settings[key][sub_key][2] = value

                if (self.settings[key][sub_key][2] == True or
                self.settings[key][sub_key][2] == False):
                    value = "1" if value else "0"

                # Ensures that comment is in the correct format; no new lines and no unnecessary
                # whitespace before or after the actual comment
                comment = self.settings[key][sub_key][4].strip()
                comment = " // {0}".format(comment) if comment != "" else ""
                comment = re.sub("[\r|\n]", "", comment)
                lines.append("{0} = {1}{2}".format(sub_key, value, comment))

            lines.append("")
        # Removes the last element from the list
        lines.pop()
        text = "\n".join(lines)
        cfg_path = path.join(sys.path[0], self.settings_filepath)
        cfg = open(cfg_path, "w")
        cfg.write(text)
        cfg.close()

    # Converts the physical board pin numbers to the BCM pin numbers
    def board_bcm(self, pin, returnPin = True):
        global bcm_pins

        index = 0
        displacement = 0
        try:
            pin = int(pin)
            displacement = (-4 if pin % 2 == 1 else 2 + (1 if pin < 10 else 0)
                + len(str(pin)))
            index = self.bcm_pins.index("({0})".format(pin)) + displacement
            displacement = 3 if pin % 2 == 1 else 7
            bcm = self.bcm_pins[index:index + displacement].strip(" GPIO\r\n")
            if bcm.isdigit():
                if returnPin:
                    return int(bcm)
                else:
                    return True
            else:
                return False
        except:
            return False

# Class to interact with the motors
class GPIOHandler:
    thread = None
    run = True # Only set to false when the program is exiting
    all_operating = False # Equivalent to the threads being paused
    clean = True # All GPIO settings have either been cleared or not instantiated
    current_time = 0.0

    # Called when the class is created
    def __init__(self):
        global PUL
        global DIR
        global stepper

        switch_interval = sys.getswitchinterval() / 100.0
        sys.setswitchinterval(switch_interval)

        self.thread = threading.Thread(target=self.runMotors)
        self.thread.daemon = True # If the program is closed forcefully,
                                  # the thread will also close
        self.thread.start()

    # The procedure which actually controls the motors
    def runMotors(self):
        global run
        global delay
        global PUL
        global DIR
        global operating
        global dirs
        global all_operating
        global rpm_0
        global clean

        resolution = 0.00001 # Seconds between step increment
        steps = [0, 0, 0]
        gpio_high = [False, False, False]
        
        while self.run:
            if not self.clean and self.all_operating:
                for i in range(len(PUL)):
                    GPIO.output(PUL[i], GPIO.HIGH if gpio_high[i] and operating[i]
                        and not rpm_0[i] else GPIO.LOW)
                    GPIO.output(DIR[i], GPIO.LOW if dirs[i] else GPIO.HIGH)
                    
                    steps[i] += 1
                    if round(delay[i] / resolution) <= steps[i]:
                        gpio_high[i] = not gpio_high[i]
                        steps[i] = 0

                sleep(resolution)

            else:
                steps = [0, 0, 0]
                sleep(0.0001)

    # Called whenever the state of the emergency stop pin changes; this allows
    # the use of either a PTM or a PTB switch
    def emergency(self, e):
        global clean
        global app

        if not self.clean:
            self.pauseThreads()
            app.startPressed()

    # Called whenever the motors need to be stopped, but the program does not
    # need to exit
    def pauseThreads(self):
        global all_operating
        global clean

        self.all_operating = False
        sleep(0.25)
        # self.cleanPins() called to prevent errors if the program is exited
        # after this procedure is called
        self.cleanPins()

    # Called whenever the motors are to be started again
    def resumeThreads(self):
        global all_operating
        global PUL
        global DIR
        global EMER
        global clean

        GPIO.setmode(GPIO.BCM)

        for i in range(len(PUL)):
            GPIO.setup(PUL[i], GPIO.OUT)
            GPIO.setup(DIR[i], GPIO.OUT)

        GPIO.setup(EMER, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(EMER, GPIO.BOTH, callback=self.emergency)

        self.all_operating = True
        self.clean = False

    # Called whenever the program is exiting; it stops the loops in the threads
    # and cleans up the GPIO settings
    def stopThreads(self):
        global run
        global clean

        self.run = False # Allows threads to exit themselves before GPIO cleanup
        sleep(0.25)
        self.cleanPins()

    def cleanPins(self):
        global clean

        if not self.clean:
            GPIO.cleanup()
            self.clean = True

def updateVersion():
    global version
    global url_main

    try:
        test_vers = get("{0}version.cfg".format(url_main))
        int_test_vers = int(str.replace(test_vers.text, ".", ""))
        int_version = int(str.replace(version, ".", ""))

        if int_test_vers > int_version and "200" in str(test_vers):
            vers_file = open(path.join(sys.path[0], "version.cfg"), "w")
            vers_file.write(test_vers.text)
            vers_file.close()

            version = test_vers.text

            script_text = get("{0}stepperHandler.py".format(url_main))
            if "200" in str(script_text):
                script = open(path.join(sys.path[0], "stepperHandler.py"), "w")
                script.write(script_text.text)
                script.close()
    except:
        pass



# Called to start the program proper
def main():
    global gpio_handler
    global app

    gpio_handler = GPIOHandler()
    app = MainWindow()
    app.mainloop() # Makes TKinter start to listen for user inputs
    updateVersion()

# Ensures the rest of the program only runs if this has not been imported as
# a module by another program
if __name__ == "__main__":
    main()