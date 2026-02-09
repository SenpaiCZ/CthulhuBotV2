from bs4 import BeautifulSoup
import sys

def verify_skip_link():
    try:
        with open('dashboard/templates/base.html', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ Error: dashboard/templates/base.html not found.")
        return False

    soup = BeautifulSoup(content, 'html.parser')

    # Check for skip link
    skip_link = soup.find('a', class_='skip-link')
    if not skip_link:
        print("❌ Error: Skip link not found.")
        return False

    if skip_link.get('href') != '#main-content':
        print(f"❌ Error: Skip link href is '{skip_link.get('href')}', expected '#main-content'.")
        return False

    if 'visually-hidden-focusable' not in skip_link.get('class', []):
        print("❌ Error: Skip link missing 'visually-hidden-focusable' class.")
        return False

    # Check for main content target
    main_content = soup.find(id='main-content')
    if not main_content:
        print("❌ Error: Element with id='main-content' not found.")
        return False

    if main_content.name != 'main':
         print(f"⚠️ Warning: Main content element is <{main_content.name}>, expected <main>. (Semantic HTML preference)")

    if str(main_content.get('tabindex')) != '-1':
        print(f"❌ Error: Main content tabindex is '{main_content.get('tabindex')}', expected '-1'.")
        return False

    print("✅ Verification Successful: Skip link and target are correctly implemented.")
    return True

if __name__ == "__main__":
    if not verify_skip_link():
        sys.exit(1)
