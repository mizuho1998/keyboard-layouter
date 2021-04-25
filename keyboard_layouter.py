import json
import math
import sys
import traceback

import pcbnew
import wx

SWITCH_REF_PREFIX = 'SW'
DIODE_REF_PREFIX = 'D'
KEY_UNIT_SIZE_MM = 19.05

KEY_OFFSET = {
    '1': 0,          # 9.525  (Footprint coordinates. 1u = 19.05, 1u/2 = 9.525)
    '1.25': 2.381,   # 11.906 (11.906 - 9.525 = 2.381)
    '1.5': 4.763,    # 14.287
    '1.75': 7.144,   # 16.668
    '2': 9.525,      # 19.05
    '2.25': 11.906,  # 21.431
    '2.5': 14.281,  # 23.812
    '2.75': 16.669,  # 26.193
    '6.25': 50.006,  # 59.531
}

KEY_ORIGIN = {
    ('1', '1'): (9.525, 9.525),
    ('1', '2'): (9.525, 9.525 * 2),
    ('1.25', '1'): (9.525 * 1.25, 9.525),
    ('1.5', '1'): (9.525 * 1.5, 9.525),
    ('1.75', '1'): (9.525 * 1.75, 9.525),
    ('2', '1'): (9.525 * 2, 9.525),
    ('2.25', '1'): (9.525 * 2.25, 9.525),
    ('2.5', '1'): (9.525 * 2.5, 9.525),
    ('2.75', '1'): (9.525 * 2.75, 9.525),
    ('6.25', '1'): (9.525 * 6.25, 9.525),
}

DEFAULT_PARAMS = {
    'json': {
        'file': '',
        'data': [],
    },
    'switch': {
        'move': True,
    },
    'diode': {
        'move': True,
        'offset_x_mm': '0',  # -8.6725
        'offset_y_mm': '0',  # 8.59
        'flip': False,
    },
}


WINDOW_SIZE = (600, 370)
MARGIN_PIX = 10
INDENT_PIX = 20

class KeyboardLayouter(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = 'Keyboard Layouter'
        self.category = 'Modify PCB'
        self.description = 'Move parts to the position specified by json'
        self.__version__ = '0.1.0'

    def Run(self):
        frame_title = '%s (%s)' % (self.name, self.version)
        gui = GUI(frame_title, self.__run)
        gui.run()

    def __run(self, params):
        self.params = params
        self.status = 'ok'
        self.messages = []

        self.board = pcbnew.GetBoard()
        self.__execute()
        pcbnew.Refresh()

        return self.status, self.messages

    def __execute(self):
        props = {
            'x': 0,
            'y': 0,
            'w': 1,
            'h': 1,
            'r': 0,
            'rx': 0,
            'ry': 0,
        }
        reset_x = reset_y = 0
        for y, row in enumerate(self.params['json']['data']):
            for element in row:
                if type(element) is dict:
                    r = element.get('r')
                    rx = element.get('rx')
                    ry = element.get('ry')

                    if r is not None:
                        props['r'] = r
                    if rx is not None:
                        props['rx'] = reset_x = rx
                    if ry is not None:
                        props['ry'] = reset_y = ry
                    if (rx is not None) or (ry is not None):
                        props['x'] = reset_x
                        props['y'] = reset_y

                    props['x'] += element.get('x', 0)
                    props['y'] += element.get('y', 0)
                    props['w'] = element.get('w', 1)
                    props['h'] = element.get('h', 1)
                else:
                    ref_id = element.split("\n")[0].strip()  # top left legend is used as ref_id
                    self.__check_key_size(ref_id, props)
                    self.__move_parts(ref_id, props)
                    props['x'] += props['w']
                    props['w'] = 1
                    props['h'] = 1
            props['x'] = reset_x
            props['y'] += 1

    def __check_key_size(self, ref_id, props):
        w, h = str(props['w']), str(props['h'])
        r = -props['r']
        flag = False

        if (KEY_OFFSET.get(w) is None) or (KEY_OFFSET.get(h) is None):
            flag = True

        if (r != 0) and (KEY_ORIGIN.get((w, h)) is None):
            flag = True

        if flag:
            self.status = 'warning'
            self.messages.append(
                '%s is ( w, h )=( %s, %s ). This size is not applicable.' % (self.__sw_ref(ref_id), w, h)
            )

    @staticmethod
    def __sw_ref(ref_id):
        return '%s%s' % (SWITCH_REF_PREFIX, ref_id)

    @staticmethod
    def __diode_ref(ref_id):
        return '%s%s' % (DIODE_REF_PREFIX, ref_id)

    @staticmethod
    def __rotate(deg, x, y, x0=0, y0=0):
        rad = math.pi * deg / 180.0
        xd = math.cos(rad) * (x - x0) + math.sin(rad) * (y - y0)
        yd = -math.sin(rad) * (x - x0) + math.cos(rad) * (y - y0)
        return xd + x0, yd + y0

    def __move_parts(self, ref_id, props):
        x, y, w, h = props['x'], props['y'], str(props['w']), str(props['h'])
        r, rx, ry = -props['r'], props['rx'], props['ry']

        x_mm = KEY_UNIT_SIZE_MM * x + KEY_OFFSET.get(w, 0)
        y_mm = KEY_UNIT_SIZE_MM * y + KEY_OFFSET.get(h, 0)

        rx_mm = KEY_UNIT_SIZE_MM * rx - KEY_ORIGIN.get((w, h), (0, 0))[0] + KEY_OFFSET.get(w, 0)
        ry_mm = KEY_UNIT_SIZE_MM * ry - KEY_ORIGIN.get((w, h), (0, 0))[1] + KEY_OFFSET.get(h, 0)
        x_mm, y_mm = self.__rotate(r, x_mm, y_mm, rx_mm, ry_mm)

        if self.params['switch']['move']:
            sw = self.board.FindModule(self.__sw_ref(ref_id))
            if sw is not None:
                sw.SetPosition(pcbnew.wxPointMM(x_mm, y_mm))
                sw.SetOrientationDegrees(r)

        if self.params['diode']['move']:
            diode = self.board.FindModule(self.__diode_ref(ref_id))
            if diode is not None:
                diode.SetPosition(pcbnew.wxPointMM(x_mm, y_mm))
                dx_mm, dy_mm = self.__rotate(r,
                                             self.params['diode']['offset_x_mm'],
                                             self.params['diode']['offset_y_mm'])
                diode.Move(pcbnew.wxPointMM(dx_mm, dy_mm))

                if self.params['diode']['move']:
                    diode.Flip(diode.GetCenter())
                diode.SetOrientationDegrees(r)

    @property
    def version(self):
        return self.__version__


class FilePanel(wx.Panel):
    def __init__(self, parent, params):
        super(FilePanel, self).__init__(parent, wx.ID_ANY)
        self.params = params

        text = wx.StaticText(self, wx.ID_ANY, 'JSON file:')

        self.textctrl = wx.TextCtrl(self, wx.ID_ANY)
        GUI.set_initial_textctrl(self.textctrl, True, self.params['json']['file'])
        self.textctrl.Bind(wx.EVT_TEXT, self.textctrl_handler)

        button = wx.Button(self, wx.ID_ANY, 'Select')
        button.Bind(wx.EVT_BUTTON, self.button_handler)

        layout = wx.BoxSizer(wx.HORIZONTAL)
        layout.Add(text, flag=wx.ALIGN_CENTER)
        layout.Add(self.textctrl, proportion=1, flag=wx.ALIGN_CENTER | wx.LEFT, border=MARGIN_PIX)
        layout.Add(button, flag=wx.ALIGN_CENTER | wx.LEFT, border=MARGIN_PIX)
        self.SetSizer(layout)

    def textctrl_handler(self, _):
        self.params['json']['file'] = self.textctrl.GetValue()

    def button_handler(self, _):
        dialog = wx.FileDialog(None, 'Select a file', '', '',
                               'JSON file(*.json)|*.json|All files|*.*',
                               wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dialog.ShowModal() == wx.ID_OK:
            self.textctrl.SetValue(dialog.GetPath())
        else:
            self.textctrl.SetValue('')

class SwitchPanel(wx.Panel):
    def __init__(self, parent, params):
        super(SwitchPanel, self).__init__(parent, wx.ID_ANY)
        self.params = params

        checkbox_move = wx.CheckBox(self, wx.ID_ANY, 'Switch')
        GUI.set_initial_checkbox(checkbox_move, True, self.params['switch']['move'])
        checkbox_move.Bind(wx.EVT_CHECKBOX, self.checkbox_move_handler)

        layout = wx.BoxSizer(wx.HORIZONTAL)
        layout.Add(checkbox_move)
        self.SetSizer(layout)

    def checkbox_move_handler(self, _):
        self.params['switch']['move'] = checkbox_move.GetValue()

class DiodePanel(wx.Panel):
    def __init__(self, parent, params):
        super(DiodePanel, self).__init__(parent, wx.ID_ANY)
        self.params = params

        checkbox_move = wx.CheckBox(self, wx.ID_ANY, 'Diode')
        GUI.set_initial_checkbox(checkbox_move, True, self.params['diode']['move'])
        checkbox_move.Bind(wx.EVT_CHECKBOX, self.checkbox_move_handler)

        panel_offset_x_mm = wx.Panel(self, wx.ID_ANY)
        text_offset_x_mm = wx.StaticText(panel_offset_x_mm, wx.ID_ANY, 'Offset x[mm]:')
        self.textctrl_offset_x_mm = wx.TextCtrl(panel_offset_x_mm, wx.ID_ANY)
        GUI.set_initial_textctrl(self.textctrl_offset_x_mm,
                             self.params['diode']['move'],
                             self.params['diode']['offset_x_mm'])
        self.textctrl_offset_x_mm.Bind(wx.EVT_TEXT, self.textctrl_offset_x_mm_handler)
        layout_offset_x_mm = wx.BoxSizer(wx.HORIZONTAL)
        layout_offset_x_mm.Add(text_offset_x_mm, flag=wx.ALIGN_CENTER)
        layout_offset_x_mm.Add(self.textctrl_offset_x_mm, flag=wx.ALIGN_CENTER | wx.LEFT, border=MARGIN_PIX)
        panel_offset_x_mm.SetSizer(layout_offset_x_mm)

        panel_offset_y_mm = wx.Panel(self, wx.ID_ANY)
        text_offset_y_mm = wx.StaticText(panel_offset_y_mm, wx.ID_ANY, 'Offset y[mm]:')
        self.textctrl_offset_y_mm = wx.TextCtrl(panel_offset_y_mm, wx.ID_ANY)
        GUI.set_initial_textctrl(self.textctrl_offset_y_mm,
                             self.params['diode']['move'],
                             self.params['diode']['offset_y_mm'])
        self.textctrl_offset_y_mm.Bind(wx.EVT_TEXT, self.textctrl_offset_y_mm_handler)
        layout_offset_y_mm = wx.BoxSizer(wx.HORIZONTAL)
        layout_offset_y_mm.Add(text_offset_y_mm, flag=wx.ALIGN_CENTER)
        layout_offset_y_mm.Add(self.textctrl_offset_y_mm, flag=wx.ALIGN_CENTER | wx.LEFT, border=MARGIN_PIX)
        panel_offset_y_mm.SetSizer(layout_offset_y_mm)

        self.checkbox_flip = wx.CheckBox(self, wx.ID_ANY, 'Flip')
        GUI.set_initial_checkbox(self.checkbox_flip, False, self.params['diode']['move'])
        self.checkbox_flip.Bind(wx.EVT_CHECKBOX, self.checkbox_flip_handler)

        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(checkbox_move)
        layout.Add(panel_offset_x_mm, flag=wx.LEFT, border=INDENT_PIX)
        layout.Add(panel_offset_y_mm, flag=wx.LEFT, border=INDENT_PIX)
        layout.Add(self.checkbox_flip, flag=wx.LEFT, border=INDENT_PIX)
        self.SetSizer(layout)

    def checkbox_move_handler(self, _):
        self.params['diode']['move'] = checkbox_move.GetValue()
        if self.params['diode']['move']:
            self.textctrl_offset_x_mm.Enable()
            self.textctrl_offset_y_mm.Enable()
            self.checkbox_flip.Enable()
        else:
            self.textctrl_offset_x_mm.Disable()
            self.textctrl_offset_y_mm.Disable()
            self.checkbox_flip.Disable()

    def textctrl_offset_x_mm_handler(self, _):
        self.params['diode']['offset_x_mm'] = self.textctrl_offset_x_mm.GetValue()

    def textctrl_offset_y_mm_handler(self, _):
        self.params['diode']['offset_y_mm'] = self.textctrl_offset_y_mm.GetValue()

    def checkbox_flip_handler(self, _):
        self.params['diode']['flip'] = self.checkbox_flip.GetValue()

class RunPanel(wx.Panel):
    def __init__(self, parent, callback, top_frame, params):
        super(RunPanel, self).__init__(parent, wx.ID_ANY)
        self.callback = callback
        self.top_frame = top_frame
        self.params = params

        button = wx.Button(self, wx.ID_ANY, 'Run')
        button.Bind(wx.EVT_BUTTON, self.button_run_handler)
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(button, 0, wx.GROW)
        self.SetSizer(layout)

    def button_run_handler(self, _):
        try:
            p = self.__pre_process(self.params)
            status, messages = self.callback(p)
            if status == 'warning':
                wx.MessageBox('\n'.join(messages), 'Warning', style=wx.OK | wx.ICON_WARNING)
            self.top_frame.Close(True)
        except IOError:
            wx.MessageBox('Keyboard Layouter cannot open this file.\n\n%s' % self.params['json']['file'],
                          'Error: File cannot be opened', style=wx.OK | wx.ICON_ERROR)
        except ValueError:
            wx.MessageBox('Keyboard Layouter cannot parse this json file.\n\n%s' % self.params['json']['file'],
                          'Error: File cannot be parsed', style=wx.OK | wx.ICON_ERROR)
        except Exception:
            t, v, tb = sys.exc_info()
            wx.MessageBox('\n'.join(traceback.format_exception(t, v, tb)),
                          'Execution failed', style=wx.OK | wx.ICON_ERROR)
        finally:
            return

    def __pre_process(self, p):
        p['json']['data'] = self.__load_json(p)
        p['diode']['offset_x_mm'] = float(p['diode']['offset_x_mm'])
        p['diode']['offset_y_mm'] = float(p['diode']['offset_y_mm'])
        return p

    def __load_json(self, p):
        with open(p['json']['file'], 'r') as f:
            json_data = json.load(f)

            # remove keyboard metadata
            if type(json_data[0]) is dict:
                json_data = json_data[1:]

        return json_data


class GUI(wx.Frame):
    def __init__(self, frame_title, callback):
        super(GUI, self).__init__(None, wx.ID_ANY, frame_title, size=WINDOW_SIZE)

        self.params = DEFAULT_PARAMS.copy()
        self.callback = callback

    def run(self):
        root_panel = wx.Panel(self, wx.ID_ANY)
        file_panel = FilePanel(root_panel, self.params)
        switch_panel = SwitchPanel(root_panel, self.params)
        diode_panel = DiodePanel(root_panel, self.params)
        run_panel = RunPanel(root_panel, self.callback, self, self.params)

        root_layout = wx.BoxSizer(wx.VERTICAL)
        root_layout.Add(file_panel, 0, wx.GROW | wx.ALL, border=MARGIN_PIX)
        root_layout.Add(switch_panel, 0, wx.GROW | wx.ALL, border=MARGIN_PIX)
        root_layout.Add(diode_panel, 0, wx.GROW | wx.ALL, border=MARGIN_PIX)
        root_layout.Add(run_panel, 0, wx.GROW | wx.ALL, border=MARGIN_PIX)
        root_panel.SetSizer(root_layout)
        root_layout.Fit(root_panel)

        self.Center()
        self.Show()

    @staticmethod
    def set_initial_textctrl(textctrl, enable, value):
        if enable:
            textctrl.Enable()
        else:
            textctrl.Disable()
        textctrl.SetValue(str(value))

    @staticmethod
    def set_initial_checkbox(checkbox, enable, value):
        if enable:
            checkbox.Enable()
        else:
            checkbox.Disable()
        checkbox.SetValue(value)


KeyboardLayouter().register()
