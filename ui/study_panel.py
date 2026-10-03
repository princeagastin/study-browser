import json
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTextBrowser, QLabel, QWidget)
from PySide6.QtGui import QFont

from ai import provider, prompts

# JavaScript to extract page text (truncated to avoid token limits)
JS_EXTRACT_TEXT = "(function(){ return document.body.innerText.substring(0, 8000); })();"
# JavaScript to get selected text
JS_GET_SELECTION = "(function(){ return window.getSelection().toString(); })();"

class StudyPanel(QFrame):
    request_close = Signal()
    # Signal to safely pass data from the background AI thread to the main UI thread
    _ai_result = Signal(bool, str, bool, str) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("studyPanel")
        self.setFixedWidth(380)
        self.setStyleSheet("""
            QFrame#studyPanel { 
                background: #ffffff; 
                border-left: 1px solid #e4e7ec; 
                padding: 0px;
            }
            QPushButton { 
                padding: 10px; border-radius: 8px; 
                background: #f0f2f5; border: 1px solid #e4e7ec; 
                text-align: left; font-weight: 500;
            }
            QPushButton:hover { background: #e8eaed; border-color: #2F5FE0; color: #2F5FE0; }
            QPushButton:disabled { background: #f9fafb; color: #9aa3b2; }
            QTextBrowser { 
                border: 1px solid #e4e7ec; border-radius: 8px; 
                padding: 12px; background: #f9fafb;
            }
            QLabel#title { font-size: 16px; font-weight: 700; color: #121417; }
            QLabel#status { font-size: 12px; color: #606a78; }
        """)
        
        # Note: If you are in dark mode, you might want to adjust the hex colors above 
        # or hook into your ui/theme.py tokens.

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title = QLabel("Study Assistant")
        title.setObjectName("title")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet("QPushButton { text-align: center; padding: 0; font-size: 16px; }")
        close_btn.clicked.connect(self.request_close.emit)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Status Label
        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("status")
        layout.addWidget(self.status_label)

        # Action Buttons
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(10)
        
        self.btn_summarize = QPushButton("📝  Summarize Page")
        self.btn_keypoints = QPushButton("🔑  Extract Key Points")
        self.btn_flashcards = QPushButton("🗂️  Generate Flashcards")
        self.btn_quiz = QPushButton("❓  Generate Quiz")
        self.btn_explain = QPushButton("💡  Explain Selection")
        
        for btn in (self.btn_summarize, self.btn_keypoints, self.btn_flashcards, self.btn_quiz, self.btn_explain):
            actions_layout.addWidget(btn)
            
        layout.addLayout(actions_layout)

        # Output Area
        self.output = QTextBrowser()
        self.output.setOpenExternalLinks(True)
        self.output.setPlaceholderText("AI responses will appear here...")
        layout.addWidget(self.output, 1)

        self._view = None
        self._ai_result.connect(self._render_result)

        # Wire up buttons
        self.btn_summarize.clicked.connect(lambda: self.run_action("summarize"))
        self.btn_keypoints.clicked.connect(lambda: self.run_action("keypoints"))
        self.btn_flashcards.clicked.connect(lambda: self.run_action("flashcards"))
        self.btn_quiz.clicked.connect(lambda: self.run_action("quiz"))
        self.btn_explain.clicked.connect(lambda: self.run_action("explain"))

    def set_view(self, view):
        """Connects the panel to the current active web view."""
        self._view = view

    def set_loading(self, is_loading):
        self.status_label.setText("Thinking..." if is_loading else "Ready.")
        for btn in (self.btn_summarize, self.btn_keypoints, self.btn_flashcards, self.btn_quiz, self.btn_explain):
            btn.setEnabled(not is_loading)

    def run_action(self, action_type):
        if not self._view:
            self.status_label.setText("No active tab.")
            return
            
        if not provider.is_available:
            self.status_label.setText("AI Offline. Is Ollama running?")
            self.output.setPlainText("Could not connect to local AI server.\n\nPlease ensure Ollama is running on port 11434.")
            return

        self.set_loading(True)
        self.output.clear()
        
        if action_type == "explain":
            self._view.page().runJavaScript(JS_GET_SELECTION, self._handle_selection)
        else:
            self._view.page().runJavaScript(JS_EXTRACT_TEXT, lambda text: self._process_text(text, action_type))

    def _handle_selection(self, text):
        if not text:
            self.set_loading(False)
            self.output.setPlainText("Please select some text on the page first.")
            return
        self._process_text(text, "explain")

    def _process_text(self, text, action_type):
        if not text:
            self.set_loading(False)
            self.output.setPlainText("Could not extract text from this page.")
            return

        prompt_map = {
            "summarize": (prompts.SUMMARIZE_SYSTEM, False),
            "keypoints": (prompts.KEY_POINTS_SYSTEM, True),
            "flashcards": (prompts.FLASHCARD_SYSTEM, True),
            "quiz": (prompts.MCQ_SYSTEM, True),
            "explain": (prompts.EXPLAIN_SYSTEM, False)
        }
        
        sys_prompt, is_json = prompt_map.get(action_type, ("", False))
        
        # Run in background thread, emit signal when done to safely update UI
        provider.generate(text, sys_prompt, is_json, 
                          callback=lambda s, r: self._ai_result.emit(s, r, is_json, action_type))

    def _render_result(self, success, result, is_json, action_type):
        self.set_loading(False)
        if not success:
            self.output.setPlainText(result)
            return
            
        if is_json:
            self._render_json(result, action_type)
        else:
            # Markdown rendering for summaries/explanations
            if hasattr(self.output, "setMarkdown"):
                self.output.setMarkdown(result)
            else:
                self.output.setPlainText(result)

    def _render_json(self, text, action_type):
        try:
            # Clean up markdown code blocks if the LLM wrapped the JSON
            clean = text.strip()
            if clean.startswith("```json"): clean = clean[7:]
            if clean.startswith("```"): clean = clean[3:]
            if clean.endswith("```"): clean = clean[:-3]
            
            data = json.loads(clean.strip())
            html = ""
            
            if action_type == "keypoints":
                for item in data:
                    html += f"<h4 style='color:#2F5FE0; margin-bottom:4px;'>{item.get('term', '')}</h4><p style='margin-top:0; color:#333;'>{item.get('definition', '')}</p>"
            elif action_type == "flashcards":
                for item in data:
                    html += f"<div style='border:1px solid #e4e7ec; padding:12px; margin-bottom:12px; border-radius:8px; background:#fff;'><b style='color:#121417;'>Front:</b> {item.get('front', '')}<br><br><b style='color:#2F5FE0;'>Back:</b> {item.get('back', '')}</div>"
            elif action_type == "quiz":
                for item in data:
                    html += f"<h4 style='color:#121417;'>{item.get('question', '')}</h4><ul style='color:#333;'>"
                    for opt in item.get('options', []):
                        html += f"<li>{opt}</li>"
                    html += f"</ul><p style='color:#30A46C; font-weight:bold;'><b>Correct Answer:</b> {item.get('correct', '')}</p><hr style='border:none; border-top:1px solid #e4e7ec; margin:16px 0;'>"
                    
            self.output.setHtml(html)
        except Exception as e:
            self.output.setPlainText("Failed to parse AI response:\n\n" + text)