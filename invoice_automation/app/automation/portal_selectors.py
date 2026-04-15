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
    home_index_url_marker: str = "/Home/Index"
    earsiv_create_link_name: str = " e-Arşiv Oluştur"
    document_currency_selector: str = "#DocumentCurrencyCode"
    getir_text: str = "Getir"
    identification_selector: str = "#txtIdentificationID"
    turmob_search_text: str = "Türmob Müsteri Sorgula"
    person_first_name_selector: str = "#txtPerson_FirstName"
    person_family_name_selector: str = "#txtPerson_FamilyName"
    city_selector: str = "#txtIl"
    district_selector: str = "#txtIlce"
    service_name_selector: str = "#MalAdi"
    price_amount_selector: str = 'input[name="Price_Amount"]'
    tax_selector: str = "#Tax_Perc0015"
    exemption_selector: str = 'select[name="istisnaListname"]'
    save_draft_button_name: str = "Taslak Kaydet   "


portal_selectors = PortalSelectors()
