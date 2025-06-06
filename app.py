from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
import os
import json
import re
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") 
genai.configure(api_key=GOOGLE_API_KEY)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/eligibility', methods=['POST'])
def check_eligibility():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        name = data.get('name', '')
        age = int(data.get('age', 0))
        income = int(data.get('income', 0))
        profession = data.get('profession', '')
        gender = data.get('gender', '')
        lang = data.get('lang', 'en')
        state = data.get('state', '')
        category = data.get('category', '')
        other_category = data.get('otherCategory', '').strip()

        # Use otherCategory if category is "Others"
        if category.lower() == 'others' and other_category:
            category = other_category

        lang_prefix = "Respond only in Hindi language." if lang == "hi" else "Respond only in English language."

        prompt = f"""
        You are an expert on Indian government schemes.

        Based on the following information:
        - Name: {name}
        - Age: {age}
        - Monthly Income: ₹{income}
        - Profession: {profession}
        - Gender: {gender}
        - State: {state}
        - Category: {category}

        Provide a list of central and state government schemes for which this user may be eligible.

        Format your response strictly in this JSON structure:
        {{
          "schemes": [
            {{
              "scheme": "Scheme Name",
              "type": "Central" or "State",
              "description": "Short description",
              "apply_link": "Official application link or 'Link not available'"
            }},
            ...
          ],
          "notes": [
            "Important Note 1",
            "Important Note 2"
          ]
        }}

        If no schemes are found, return:
        {{
          "schemes": [],
          "notes": ["No schemes found for the user."]
        }}

        Ensure as many apply_link values as possible are valid official government or scheme-specific pages (e.g. .gov.in, .nic.in, or official domains like mandhaan.in). If no direct application link is available, provide the base URL or relevant government page.

        Only return 'Link not available' if absolutely no link exists.

        {lang_prefix}
        """

        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        # Extract JSON substring from response
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        json_text = match.group(0) if match else raw_text
        parsed = json.loads(json_text)

        trusted_domains = ['.gov.in', '.nic.in', 'mandhaan.in', 'npscra.nsdl.co.in']

        def is_valid_gov_link(url):
            try:
                parsed_url = urlparse(url)
                domain = parsed_url.netloc
                return any(trusted in domain for trusted in trusted_domains)
            except:
                return False

        # Process links
        for scheme in parsed.get("schemes", []):
            link = scheme.get("apply_link", "").strip()

            if link.startswith("http://") or link.startswith("https://"):
                # Special handling for broken known links
                if "socialwelfare.delhi.gov.in/content/pension-schemes" in link:
                    scheme["apply_link"] = "https://socialwelfare.delhi.gov.in"
                elif is_valid_gov_link(link):
                    scheme["apply_link"] = link
                else:
                    scheme["apply_link"] = link  # Accept links from trusted but non-.gov domains
            else:
                scheme["apply_link"] = "Link not available"

        # Sort schemes: ones with links first
        sorted_schemes = sorted(
            parsed.get("schemes", []),
            key=lambda x: 0 if x["apply_link"] != "Link not available" else 1
        )

        return jsonify({
            "greeting": f"{'नमस्ते' if lang == 'hi' else 'Hi'} {name}, {'योजना पाल में आपका स्वागत है!' if lang == 'hi' else 'welcome to Yojana Pal!'}",
            "schemes": sorted_schemes,
            "notes": parsed.get("notes", ["कृपया आधार और आवश्यक दस्तावेज़ तैयार रखें।" if lang == "hi" else "Please keep Aadhaar and required documents ready."])
        })

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Something went wrong while fetching schemes."}), 500

if __name__ == '__main__':

    app.run(debug=True, host='localhost', port=5000)