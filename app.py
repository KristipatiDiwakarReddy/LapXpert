from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import requests, json, os
from amazon_paapi import AmazonApi
from dotenv import load_dotenv
import re

load_dotenv()
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Required for session

ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG")
OPENROUTER_API_KEY = os.getenv("OPEN_ROUTER_API_KEY")
REGION = "IN"

amazon = AmazonApi(ACCESS_KEY, SECRET_KEY, ASSOCIATE_TAG, REGION)

@app.route('/')
def form():
    return render_template('form.html')

@app.route('/predict', methods=['POST'])
def predict():

    intended_use = request.form['intended_use']
    screen_res = request.form['screen_resolution']
    battery_life = request.form['battery_life']
    os_pref = request.form['os']
    price = int(request.form['price'])  # Make sure it's int

    print("Received form data:", intended_use, screen_res, battery_life, os_pref, price)

    # 🧠 Construct prompt based on price
    prompt = f"""
    Suggest laptop specifications based on:
    - Intended Use: {intended_use}
    - Screen Resolution: {screen_res}
    - Battery Life: {battery_life}
    - OS: {os_pref}
    """
    if price <= 100000:
        prompt += f"- Maximum Budget: ₹{price}\n"

    prompt += """
    Respond in this exact JSON format:
    {
        "Processor": "...",
        "RAM and Storage": "...",
        "Graphics Card": "...",
        "Display": "...",
        "Battery": "...",
        "Notes": "Mention any trade-offs, limitations, or recommendations based on budget and use-case"
    }
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "<YOUR_SITE_URL>",
        "X-Title": "AI TUBER"
    }

    payload = {
        "model": "tngtech/deepseek-r1t2-chimera:free",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    try:
        print("📝 Prompt for LLM:\n", prompt)
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )

        print("🔄 Response Status Code:", response.status_code)
        print("📦 Raw Response Text:\n", response.text)

        response.raise_for_status()
        ai_response = response.json()['choices'][0]['message']['content']

        print("🧠 Raw LLM Content:\n", ai_response)

        # Extract JSON object
        match = re.search(r"```json\s*(\{.*?\})\s*```", ai_response, re.DOTALL)
        if match:
            cleaned_json_str = match.group(1).strip()
        else:
            match = re.search(r"(\{.*?\})", ai_response, re.DOTALL)
            if match:
                cleaned_json_str = match.group(1).strip()
            else:
                raise ValueError("No JSON object found in LLM response.")

        predicted_specs = json.loads(cleaned_json_str)
        print("✅ Parsed Specs Dict:\n", predicted_specs)

        # Fetch Amazon results

        predicted_specs = {'Processor': 'Intel Core i5 (11th Gen or newer) or AMD Ryzen 5 5500U/5600U', 'RAM and Storage': '8GB RAM (16GB recommended for multitasking) + 256GB/512GB SSD', 'Graphics Card': 'Integrated (Intel Iris Xe or AMD Radeon Graphics). No dedicated GPU needed for business tasks.', 'Display': '14" or 15.6" 1080p IPS panel (non-glossy recommended for office use)', 'Battery': '2-3 hours of real-world use (expect lower runtime with heavy multitasking/video calls)', 'Notes': 'Trade-off: Battery life is below average for business laptops (typical models offer 8-10hrs). Recommend frequent charger access or portable power bank. Prioritize lighter Ultrabooks (e.g., Dell XPS 13, Lenovo ThinkPad X/T series) for portability. Upgrade RAM/SSD if budget allows for future-proofing.'}
        keywords = f"{predicted_specs.get('Processor', '')} {predicted_specs.get('RAM and Storage', '')} laptop"

        keywords = "best laptops"

        if price <= 100000:
            max_price_for_api = int(str(price) + "00")
            print(f"max price: ₹{max_price_for_api}")
            search_result = amazon.search_items(keywords=keywords, search_index="Electronics", item_count=5, max_price=max_price_for_api, sort_by="Relevance")
        else:
            search_result = amazon.search_items(keywords=keywords, search_index="Electronics", item_count=5, sort_by="Relevance")

        items = search_result.items if search_result and search_result.items else []

        laptops = []
        for item in items:
            laptops.append({
                "title": item.item_info.title.display_value if item.item_info.title else "No title",
                "url": item.detail_page_url or "#",
                "image": item.images.primary.large.url if item.images and item.images.primary else "",
                "price": item.offers.listings[0].price.display_amount if item.offers else "Price not available"
            })

        print("Amazon Search Results:", laptops)

        # Store in session to access on /results page
        session['specs'] = predicted_specs
        session['laptops'] = laptops
        session['notes'] = predicted_specs.get("Notes", "No additional notes provided.")

        return redirect(url_for('results'))

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error": "Something went wrong", "details": str(e)}), 500


@app.route('/results')
def results():
    specs = session.get('specs', {})
    laptops = session.get('laptops', [])
    return render_template('results.html', specs=specs, laptops=laptops)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)