from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QMessageBox,
    QCheckBox,
)


class AccountDialog(QDialog):
    def __init__(self, cloud, parent=None):
        super().__init__(parent)

        self.cloud = cloud

        self.setWindowTitle("StudyBrowse Account")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        title = QLabel("StudyBrowse Account")
        title.setStyleSheet(
            "font-size: 20px; font-weight: bold;"
        )
        layout.addWidget(title)

        self.status = QLabel(
            "Sign in to sync your StudyBrowse data."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        form = QFormLayout()

        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")

        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        form.addRow("Username", self.username)
        form.addRow("Password", self.password)

        layout.addLayout(form)

        self.show_password = QCheckBox("Show password")
        self.show_password.toggled.connect(
            self._toggle_password_visibility
        )
        layout.addWidget(self.show_password)

        self.login_button = QPushButton("Sign in")
        self.login_button.clicked.connect(self.login)

        self.register_button = QPushButton("Create account")
        self.register_button.clicked.connect(self.register)

        self.logout_button = QPushButton("Log out")
        self.logout_button.clicked.connect(self.logout)
        self.logout_button.setVisible(False)

        layout.addWidget(self.login_button)
        layout.addWidget(self.register_button)
        layout.addWidget(self.logout_button)

        self.refresh_state()

    def _toggle_password_visibility(self, visible):
        if visible:
            self.password.setEchoMode(
                QLineEdit.EchoMode.Normal
            )
        else:
            self.password.setEchoMode(
                QLineEdit.EchoMode.Password
            )

    def refresh_state(self):
        if self.cloud.logged_in:
            username = self.cloud.user["username"]

            self.status.setText(
                f"Signed in as <b>{username}</b>"
            )

            self.username.setVisible(False)
            self.password.setVisible(False)
            self.show_password.setVisible(False)

            self.login_button.setVisible(False)
            self.register_button.setVisible(False)
            self.logout_button.setVisible(True)

        else:
            self.status.setText(
                "Sign in to sync your StudyBrowse data."
            )

            self.username.setVisible(True)
            self.password.setVisible(True)
            self.show_password.setVisible(True)

            self.login_button.setVisible(True)
            self.register_button.setVisible(True)
            self.logout_button.setVisible(False)

    def login(self):
        username = self.username.text().strip()
        password = self.password.text()

        if not username or not password:
            QMessageBox.warning(
                self,
                "Missing information",
                "Enter your username and password.",
            )
            return

        try:
            user = self.cloud.login(
                username,
                password,
            )

            QMessageBox.information(
                self,
                "Login successful",
                f"Welcome, {user['username']}!",
            )

            self.refresh_state()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Login failed",
                str(exc),
            )

    def register(self):
        username = self.username.text().strip()
        password = self.password.text()

        if not username or not password:
            QMessageBox.warning(
                self,
                "Missing information",
                "Enter a username and password.",
            )
            return

        try:
            user = self.cloud.register(
                username,
                password,
            )

            QMessageBox.information(
                self,
                "Account created",
                f"Welcome to StudyBrowse, {user['username']}!",
            )

            self.refresh_state()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Registration failed",
                str(exc),
            )

    def logout(self):
        self.cloud.logout()
        self.refresh_state()