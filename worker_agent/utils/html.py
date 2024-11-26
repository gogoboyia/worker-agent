import json

from bs4 import BeautifulSoup, Comment


def clean_html_with_bs(content):
    soup = BeautifulSoup(content, "html.parser")
    
    for element in soup.find_all("path"):
        element.decompose()
        
    for element in soup.find_all("script"):
        element.decompose()
        
    for element in soup.find_all("style"):
        element.decompose()
        
    for element in soup.find_all("link"):
        element.decompose()
        
    for element in soup.find_all("meta"):
        element.decompose()
        
    for element in soup.find_all("svg"):
        element.decompose()
    for element in soup.find_all("noscript"):
        element.decompose()
    
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
        
    allowed_attributes = {"id", "href", "src", "alt", "title", "name", "type", "value", "placeholder"}
    
    for element in soup.find_all():
        attributes_to_remove = [attr for attr in element.attrs if attr not in allowed_attributes]
        for attr in attributes_to_remove:
            element.attrs.pop(attr)
    
    return str(soup)


def generate_xpath_map(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    xpath_map = {}

    def get_xpath(element):
        components = []
        for parent in element.parents:
            if parent.name:
                siblings = parent.find_all(element.name, recursive=False)
                if len(siblings) > 1:
                    index = siblings.index(element) + 1
                    components.append(f"{parent.name}[{index}]")
                else:
                    components.append(parent.name)
        components.reverse()
        components.append(element.name)
        xpath = "/" + "/".join(components)
        return xpath.replace("[document]/", "", 1)

    interactive_elements = soup.find_all(["a", "button", "input", "textarea", "select"])

    for element in interactive_elements:
        xpath = get_xpath(element)
        details = {}
        attributes = {key: value for key, value in element.attrs.items() if key in ["placeholder", "id", "href"] and value}
        if attributes:
          details['attributes'] = attributes
        text = element.get_text(strip=True).replace("\\n", "")
        if text:
          details['text'] = text
        
        if details:
          xpath_map[xpath] = details

    return json.dumps(xpath_map)