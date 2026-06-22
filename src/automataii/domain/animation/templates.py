HTML_VIEWER_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Body Parts Viewer</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
        }}
        .orig-image {{
            max-width: 100%;
            margin-bottom: 20px;
        }}
        .segmentation {{
            max-width: 100%;
            margin-bottom: 20px;
        }}
        .part-card {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            width: 300px;
        }}
        .part-card h3 {{
            margin-top: 0;
            color: #333;
        }}
        .part-image {{
            max-width: 100%;
            height: auto;
            display: block;
            margin-bottom: 10px;
        }}
        .part-svg {{
            max-width: 100%;
            height: auto;
            display: block;
            margin-bottom: 10px;
            background-color: #f0f0f0;
        }}
        .animation-container {{
            margin-top: 15px;
            border-top: 1px solid #eee;
            padding-top: 10px;
        }}
        .animation-container h4 {{
            margin-top: 0;
            color: #555;
        }}
        .part-animation {{
            max-width: 100%;
            height: auto;
            display: block;
            border: 1px dashed #ccc;
            background-color: #f9f9f9;
        }}
        }}
        .tabs {{
            display: flex;
            margin-bottom: 10px;
        }}
        .tab {{
            padding: 8px 16px;
            background-color: #e0e0e0;
            border: none;
            cursor: pointer;
            margin-right: 5px;
            border-radius: 4px 4px 0 0;
        }}
        .tab.active {{
            background-color: #007bff;
            color: white;
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}
    </style>
</head>
<body>
    <h1>Character Body Part Segmentation Results</h1>

    <div class="tabs">
        <button class="tab active" onclick="openTab('preview')">Preview</button>
        <button class="tab" onclick="openTab('parts')">Body Parts</button>
    </div>

    <div id="preview" class="tab-content active">
        <h2>Source Image and Segmentation Result</h2>
        <img src="{texture_path}" alt="Source image" class="orig-image">
        <img src="{segmentation_path}" alt="Segmentation result" class="segmentation">
    </div>

    <div id="parts" class="tab-content">
        <h2>Body Part List</h2>
        <div class="container">
            {part_cards}
        </div>
    </div>

    <script>
        function openTab(tabName) {{
            // Hide all tab contents
            const tabContents = document.getElementsByClassName('tab-content');
            for (let i = 0; i < tabContents.length; i++) {{
                tabContents[i].classList.remove('active');
            }}

            // Deactivate all tabs
            const tabs = document.getElementsByClassName('tab');
            for (let i = 0; i < tabs.length; i++) {{
                tabs[i].classList.remove('active');
            }}

            // Show the selected tab content
            document.getElementById(tabName).classList.add('active');

            // Activate the clicked tab
            event.currentTarget.classList.add('active');
        }}
    </script>
</body>
</html>
"""

PART_CARD_TEMPLATE = """
<div class="part-card">
    <h3>{part_name}</h3>
    <img src="{image_path}" alt="{part_name}" class="part-image">
    <img src="{svg_path}" alt="{part_name} SVG" class="part-svg">
    {animation_element}
</div>
"""
