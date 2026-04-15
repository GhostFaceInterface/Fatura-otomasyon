"""Portal URLs and locator labels used by Playwright automation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PortalSelectors:
    """Human-readable locators captured from the portal login flow."""

    username_textbox_name: str = "Kullanıcı Adı"
    password_textbox_name: str = "Şifre"
    login_button_name: str = "Giriş"
    two_factor_code_placeholder: str = "Kod"
    two_factor_submit_button_name: str = "Doğrula"
    earsiv_menu_link_name: str = " e-Arşiv "
    verification_url_marker: str = "/User/VerificationUser"


portal_selectors = PortalSelectors()
