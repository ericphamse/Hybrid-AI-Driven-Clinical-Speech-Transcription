
from kivy.uix.screenmanager import Screen
from kivy.uix.image import Image
from kivy.uix.label import Label
import os
import pypdfium2 as pdfium


class PDFPreviewScreen(Screen):
    def on_pre_enter(self, *args):
        self.display_pdf_images()

    def display_pdf_images(self):
        self.ids.preview_box.clear_widgets()
        # Remove previously generated images
        for fname in os.listdir(os.getcwd()):
            if fname.startswith('pdf_page_') and fname.endswith('.png'):
                try:
                    os.remove(os.path.join(os.getcwd(), fname))
                except Exception:
                    pass
        pdf_path = os.path.abspath('test.pdf')
        if not os.path.exists(pdf_path):
            self._show_error("No PDF found. Please save a session to generate test.pdf.")
            return
        try:
            pdf = pdfium.PdfDocument(pdf_path)
            n_pages = len(pdf)
            for i in range(n_pages):
                page = pdf[i]
                pil_image = page.render(scale=2).to_pil()
                img_path = os.path.join(os.getcwd(), f'pdf_page_{i}.png')
                pil_image.save(img_path, 'PNG')
                kivy_img = Image(source=img_path, allow_stretch=True, keep_ratio=True)
                kivy_img.size_hint_y = None
                def _fit_to_box(instance, *args):
                    texture = instance.texture
                    if not texture:
                        return
                    iw, ih = texture.size
                    box_width = self.ids.preview_box.width
                    if iw == 0:
                        return
                    instance.width = box_width
                    instance.height = box_width * (ih / float(iw))
                kivy_img.bind(texture=_fit_to_box)
                self.ids.preview_box.bind(width=lambda *_: _fit_to_box(kivy_img))
                self.ids.preview_box.add_widget(kivy_img)
            pdf.close()
        except Exception as e:
            self._show_error(f"Failed to render PDF: {e}")
            return

    def _show_error(self, message: str):
        self.ids.preview_box.add_widget(
            Label(text=message, halign='center', valign='middle')
        )
