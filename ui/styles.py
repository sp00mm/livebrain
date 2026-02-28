BG_PRIMARY = '#1e1e1e'
BG_SECONDARY = '#2a2a2a'
BG_BUTTON = '#3a3a3a'
BG_HOVER = '#454545'
BG_ICON_HOVER = '#404040'
BG_CARD = '#252525'
BG_CARD_HOVER = '#2d2d2d'
BG_RESPONSE = '#1a1a1a'

TEXT_PRIMARY = '#e0e0e0'
TEXT_SECONDARY = '#888888'
TEXT_LABEL = '#b0b0b0'
TEXT_DIM = '#666666'
TEXT_SECTION = '#707070'

BORDER_COLOR = '#4a4a4a'
BORDER_HOVER = '#555555'
BORDER_FOCUS = '#505050'

ACCENT = '#4CAF50'
ACCENT_BG = '#2d4a2d'
ACCENT_BORDER = '#3a5a3a'
DANGER_BG = '#4a2020'
DANGER_BORDER = '#5a2525'
RECORDING_COLOR = '#ff4444'
ERROR_COLOR = '#ff6b6b'
USER_COLOR = '#5fb85f'

FEED_DIVIDER = '#3a3a3a'
FEED_QUESTION_BG = '#2a2a2a'
FEED_ANSWER_ACTIVE = '#e0e0e0'
FEED_ANSWER_FADED = '#999999'
FEED_STATUS_COLOR = '#707070'

FONT_FAMILY = '-apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif'
FONT_SIZE = '13px'

BASE_STYLE = f'''
QWidget {{
    background: transparent;
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE};
}}
QPushButton {{
    background-color: {BG_BUTTON};
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    padding: 6px 12px;
    color: {TEXT_PRIMARY};
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
}}
QPushButton:pressed {{
    background-color: {BG_SECONDARY};
}}
QPushButton#downloadBtn {{
    background-color: {ACCENT};
    border: none;
    font-weight: 500;
}}
QPushButton#iconBtn {{
    background: transparent;
    border: none;
    padding: 4px;
    border-radius: 4px;
    min-width: 24px;
    max-width: 24px;
}}
QPushButton#iconBtn:hover {{
    background-color: {BG_ICON_HOVER};
}}
'''

INPUT_STYLE = f'''
QLineEdit {{
    background-color: {BG_PRIMARY};
    border: 1px solid {BG_BUTTON};
    border-radius: 8px;
    padding: 10px 12px;
    color: {TEXT_PRIMARY};
    font-size: {FONT_SIZE};
}}
QLineEdit:focus {{
    border-color: {BORDER_FOCUS};
}}
QTextEdit {{
    background-color: {BG_PRIMARY};
    border: none;
    border-radius: 8px;
    padding: 12px;
    color: {TEXT_PRIMARY};
    font-size: {FONT_SIZE};
}}
QTextEdit#responseBox {{
    background-color: {BG_RESPONSE};
    border-radius: 10px;
}}
QComboBox {{
    background-color: transparent;
    border: none;
    padding: 4px 8px;
    color: {TEXT_PRIMARY};
    font-size: {FONT_SIZE};
}}
QComboBox:hover {{
    background-color: #353535;
    border-radius: 4px;
}}
QComboBox::drop-down {{
    border: none;
    width: 16px;
}}
QComboBox::down-arrow {{
    image: none;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_SECONDARY};
    border: 1px solid {BG_ICON_HOVER};
    border-radius: 6px;
    selection-background-color: {BG_ICON_HOVER};
    color: {TEXT_PRIMARY};
    padding: 4px;
}}
QComboBox#settingsCombo {{
    background-color: {BG_PRIMARY};
    border: 1px solid {BG_BUTTON};
    border-radius: 8px;
    padding: 8px 12px;
}}
'''

CARD_STYLE = f'''
QFrame#questionRow {{
    background-color: {BG_CARD};
    border-radius: 6px;
}}
QFrame#questionRow:hover {{
    background-color: {BG_CARD_HOVER};
}}
'''

LABEL_STYLE = f'''
QLabel {{
    color: {TEXT_LABEL};
}}
QLabel#sectionLabel {{
    color: {TEXT_SECTION};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
QLabel#liveLabel {{
    font-weight: 600;
    font-size: {FONT_SIZE};
}}
QLabel#transcriptUser {{
    color: {USER_COLOR};
    font-size: {FONT_SIZE};
}}
QLabel#transcriptOther {{
    color: #ffffff;
    font-size: {FONT_SIZE};
}}
'''

SCROLL_STYLE = '''
QScrollArea {
    border: none;
    background: transparent;
}
'''

STYLE_SHEET = BASE_STYLE + INPUT_STYLE + LABEL_STYLE + CARD_STYLE + SCROLL_STYLE
