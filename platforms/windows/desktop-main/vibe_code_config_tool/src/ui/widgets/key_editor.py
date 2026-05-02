"""按键编辑器。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
)

from ...comm.protocol import MacroAction
from ...core.keycodes import KEYCODES_BY_CATEGORY, KeyType, get_keycode_name
from ...core.keymap import MAX_DESCRIPTION_LEN, KeyBinding


class KeyEditor(QFrame):
    """编辑单个按键的描述、类型和数据。Mode 3 下的 Key2/Key3 支持终端Agent审批模式。"""

    binding_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._binding = KeyBinding()
        self._updating = False
        self._mode_id = -1      # 当前模式ID（-1 表示未设置）
        self._key_index = -1    # 当前按键索引（0-3）
        self._setup_ui()
    
    def set_mode_and_key(self, mode_id: int, key_index: int):
        """设置模式和按键索引（用于 Mode 3 的特殊处理）"""
        self._mode_id = mode_id
        self._key_index = key_index

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        desc_group = QGroupBox("按键描述")
        desc_layout = QVBoxLayout(desc_group)
        desc_hint = QLabel("你对它的命名，显示在键盘屏幕上 (max 20 ASCII字符)")
        desc_hint.setStyleSheet("color: #888; font-size: 11px;")
        desc_layout.addWidget(desc_hint)
        self.desc_edit = QLineEdit()
        self.desc_edit.setMaxLength(MAX_DESCRIPTION_LEN)
        self.desc_edit.setPlaceholderText("例: Ctrl+C, open CMD...")
        self.desc_edit.textChanged.connect(self._on_desc_changed)
        desc_layout.addWidget(self.desc_edit)
        layout.addWidget(desc_group)

        type_group = QGroupBox("按键类型")
        type_layout = QVBoxLayout(type_group)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["快捷键", "宏", "终端审批"])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.type_combo)
        layout.addWidget(type_group)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_shortcut_panel())
        self.stack.addWidget(self._build_macro_panel())
        self.stack.addWidget(self._build_terminal_agent_panel())
        layout.addWidget(self.stack)
    
    def _is_terminal_agent_key(self) -> bool:
        """判断当前按键是否为 Mode 3 的审批按键（Key2 或 Key3）"""
        return self._mode_id == 3 and self._key_index in (1, 2)

    def _build_shortcut_panel(self) -> QFrame:
        panel = QFrame()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("键码列表 (修饰键在前, 普通键在后):"))

        self.shortcut_list = QListWidget()
        self.shortcut_list.setMaximumHeight(120)
        layout.addWidget(self.shortcut_list)

        row = QHBoxLayout()
        self.sc_add_combo = QComboBox()
        self.sc_add_combo.setMinimumWidth(180)
        self._populate_all_keys(self.sc_add_combo)
        row.addWidget(self.sc_add_combo)

        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._add_shortcut_key)
        row.addWidget(add_btn)

        remove_btn = QPushButton("删除")
        remove_btn.clicked.connect(self._remove_shortcut_key)
        row.addWidget(remove_btn)

        layout.addLayout(row)
        layout.addStretch()
        return panel

    def _build_macro_panel(self) -> QFrame:
        panel = QFrame()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("宏步骤列表 (动作 + 参数):"))

        self.macro_list = QListWidget()
        self.macro_list.setMaximumHeight(150)
        layout.addWidget(self.macro_list)

        action_row = QHBoxLayout()
        action_row.addWidget(QLabel("动作:"))
        self.mc_action_combo = QComboBox()
        self.mc_action_combo.addItem("按下按键", MacroAction.DOWN_KEY)
        self.mc_action_combo.addItem("释放按键", MacroAction.UP_KEY)
        self.mc_action_combo.addItem("释放全部按键", MacroAction.UP_ALLKEY)
        self.mc_action_combo.addItem("延时", MacroAction.DELAY)
        self.mc_action_combo.currentIndexChanged.connect(self._on_macro_action_changed)
        action_row.addWidget(self.mc_action_combo)
        layout.addLayout(action_row)

        param_row = QHBoxLayout()
        param_row.addWidget(QLabel("参数:"))
        self.mc_key_combo = QComboBox()
        self.mc_key_combo.setMinimumWidth(160)
        self._populate_all_keys(self.mc_key_combo)
        param_row.addWidget(self.mc_key_combo)

        self.mc_delay_spin = QSpinBox()
        self.mc_delay_spin.setRange(1, 255)
        self.mc_delay_spin.setValue(100)
        self.mc_delay_spin.setSuffix(" (约 3ms)")
        self.mc_delay_spin.setVisible(False)
        param_row.addWidget(self.mc_delay_spin)
        layout.addLayout(param_row)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("添加步骤")
        add_btn.clicked.connect(self._add_macro_step)
        btn_row.addWidget(add_btn)

        remove_btn = QPushButton("删除步骤")
        remove_btn.clicked.connect(self._remove_macro_step)
        btn_row.addWidget(remove_btn)

        layout.addLayout(btn_row)
        layout.addStretch()
        return panel

    def _populate_all_keys(self, combo: QComboBox):
        combo.clear()
        for category, title in [
            ("modifier", "--- 修饰键 ---"),
            ("alpha", "--- 字母 ---"),
            ("number", "--- 数字 ---"),
            ("basic", "--- 基础键 ---"),
            ("function", "--- 功能键 ---"),
            ("control", "--- 控制键 ---"),
            ("arrow", "--- 方向键 ---"),
            ("numpad", "--- 小键盘 ---"),
        ]:
            items = KEYCODES_BY_CATEGORY.get(category, [])
            if not items:
                continue
            combo.addItem(title, -1)
            for name, code in items:
                combo.addItem(f"  {name} (0x{code:02X})", code)
    
    def _build_terminal_agent_panel(self) -> QFrame:
        """Mode 3 终端Agent审批操作选择面板"""
        panel = QFrame()
        layout = QVBoxLayout(panel)
        
        # 帮助信息
        info_label = QLabel(
            "Mode 3 终端Agent审批模式：\n"
            "此按键自动处理来自终端的审批请求。\n"
            "系统会自动提取请求ID并输入审批命令。"
        )
        info_label.setStyleSheet("color: #666; font-size: 11px; background-color: #f5f5f5; padding: 8px; border-radius: 4px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 操作说明
        action_group = QGroupBox("操作类型")
        action_layout = QVBoxLayout(action_group)
        
        self.terminal_agent_combo = QComboBox()
        self.terminal_agent_combo.addItem("同意 (allow-once)", 0)
        self.terminal_agent_combo.addItem("拒绝 (deny)", 1)
        self.terminal_agent_combo.currentIndexChanged.connect(self._on_terminal_agent_changed)
        action_layout.addWidget(self.terminal_agent_combo)
        
        layout.addWidget(action_group)
        layout.addStretch()
        
        return panel

    def set_binding(self, binding: KeyBinding):
        self._updating = True
        self._binding = binding

        self.desc_edit.setText(binding.description)
        
        # Mode 3 的 Key2/Key3 自动设置为 TERMINAL_AGENT 类型
        if self._is_terminal_agent_key():
            if binding.key_type != KeyType.TERMINAL_AGENT:
                binding.key_type = KeyType.TERMINAL_AGENT
        
        self.type_combo.setCurrentIndex(binding.key_type)
        self.stack.setCurrentIndex(binding.key_type)

        self.shortcut_list.clear()
        for code in binding.keycodes:
            self.shortcut_list.addItem(f"{get_keycode_name(code)} (0x{code:02X})")

        # 对于 TERMINAL_AGENT，设置操作类型（0=allow, 1=deny）
        if binding.key_type == KeyType.TERMINAL_AGENT and binding.keycodes:
            self.terminal_agent_combo.setCurrentIndex(binding.keycodes[0] if binding.keycodes[0] < 2 else 0)
        
        self._refresh_macro_list()
        self._updating = False

    def _refresh_macro_list(self):
        self.macro_list.clear()
        action_names = {
            MacroAction.NO_OP: "NOP",
            MacroAction.DOWN_KEY: "按下按键",
            MacroAction.UP_KEY: "释放按键",
            MacroAction.DELAY: "延时",
            MacroAction.UP_ALLKEY: "释放全部按键",
        }
        data = self._binding.macro_data
        for i in range(0, len(data) - 1, 2):
            action, param = data[i], data[i + 1]
            action_name = action_names.get(action, f"未知动作 {action}")
            if action == MacroAction.DELAY:
                self.macro_list.addItem(f"{action_name} {param} (约 3ms)")
            elif action == MacroAction.UP_ALLKEY:
                self.macro_list.addItem(action_name)
            else:
                self.macro_list.addItem(f"{action_name} {get_keycode_name(param)}")

    def _emit_change(self):
        if not self._updating:
            self.binding_changed.emit(self._binding)

    def _on_desc_changed(self, text: str):
        ascii_text = text.encode("ascii", errors="ignore").decode("ascii")
        if ascii_text != text:
            self._updating = True
            cursor_pos = self.desc_edit.cursorPosition()
            self.desc_edit.setText(ascii_text)
            self.desc_edit.setCursorPosition(min(cursor_pos, len(ascii_text)))
            self._updating = False
        self._binding.description = ascii_text[:MAX_DESCRIPTION_LEN]
        self._emit_change()

    def _on_type_changed(self, index: int):
        self.stack.setCurrentIndex(index)
        self._binding.key_type = index
        self._emit_change()

    def _add_shortcut_key(self):
        code = self.sc_add_combo.currentData()
        if code is not None and code >= 0:
            self._binding.keycodes.append(code)
            self.shortcut_list.addItem(f"{get_keycode_name(code)} (0x{code:02X})")
            self._emit_change()

    def _remove_shortcut_key(self):
        row = self.shortcut_list.currentRow()
        if row >= 0:
            self._binding.keycodes.pop(row)
            self.shortcut_list.takeItem(row)
            self._emit_change()

    def _on_macro_action_changed(self, _index: int):
        action = self.mc_action_combo.currentData()
        is_delay = action == MacroAction.DELAY
        is_no_param = action == MacroAction.UP_ALLKEY
        self.mc_key_combo.setVisible(not is_delay and not is_no_param)
        self.mc_delay_spin.setVisible(is_delay)

    def _add_macro_step(self):
        action = self.mc_action_combo.currentData()
        if action is None:
            return

        if action == MacroAction.DELAY:
            param = self.mc_delay_spin.value()
        elif action == MacroAction.UP_ALLKEY:
            param = 0
        else:
            param = self.mc_key_combo.currentData()
            if param is None or param < 0:
                return

        self._binding.macro_data.extend([action, param])
        self._refresh_macro_list()
        self._emit_change()

    def _remove_macro_step(self):
        row = self.macro_list.currentRow()
        if row < 0:
            return

        index = row * 2
        if index + 1 < len(self._binding.macro_data):
            del self._binding.macro_data[index:index + 2]
            self._refresh_macro_list()
            self._emit_change()
    
    def _on_terminal_agent_changed(self, index: int):
        """处理终端Agent操作类型变化"""
        if not self._updating:
            # 将操作类型 (0=allow, 1=deny) 存储在 keycodes[0]
            if self._binding.keycodes:
                self._binding.keycodes[0] = index
            else:
                self._binding.keycodes = [index]
            self._emit_change()
