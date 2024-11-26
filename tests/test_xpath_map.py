from worker_agent.utils.html import generate_xpath_map

# Path to the HTML file
html_file_path = "tests/youtube_page_search.html"

# Read the HTML content from the file
with open(html_file_path, "r", encoding="utf-8") as file:
    html_content = file.read()

# Generate the XPath map
result = generate_xpath_map(html_content)

# Print the result
print(result)
