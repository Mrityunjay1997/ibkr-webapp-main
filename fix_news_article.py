from pathlib import Path

path = Path('templates/morfeo.html')
text = path.read_text(encoding='utf-8')
start = text.find('function openNewsArticleModal')
if start == -1:
    raise SystemExit('function openNewsArticleModal not found')

# Find the end of the current function by matching braces.
brace = 0
in_str = False
escape = False
end_func = None
for i, ch in enumerate(text[start:], start):
    if ch == '\\' and not escape:
        escape = True
        continue
    if ch in ('"', "'") and not escape:
        in_str = not in_str
    if not in_str:
        if ch == '{':
            brace += 1
        elif ch == '}':
            brace -= 1
            if brace == 0:
                end_func = i + 1
                break
    escape = False

if end_func is None:
    raise SystemExit('Could not determine end of function')

new_func = '''                    function cleanNewsArticleText(rawText) {
                        if (!rawText) return '';

                        var normalized = rawText
                            .replace(/<br\\s*\\/?/gi, '\\n')
                            .replace(/<\\/p>/gi, '\\n\\n')
                            .replace(/<\\/h[1-6]>/gi, '\\n\\n')
                            .replace(/<li>/gi, '- ')
                            .replace(/<\\/li>/gi, '\\n');

                        var temp = document.createElement('div');
                        temp.innerHTML = normalized;
                        var text = temp.textContent || temp.innerText || '';

                        text = text.replace(/\\u00A0/g, ' ');
                        text = text.replace(/\\r\\n|\\r/g, '\\n');
                        text = text.replace(/\\n{3,}/g, '\\n\\n');
                        text = text.replace(/[ \\t]+/g, ' ');
                        text = text.replace(/^[ \\t\\n]+|[ \\t\\n]+$/g, '');

                        return text;
                    }

                    function openNewsArticleModal(provider, articleId) {
                        // Show modal with loading state
                        $('#newsArticleModal').modal('show');
                        $('#newsArticleContent').html('<div style="text-align:center;color:#888;">Loading article...</div>');

                        // Fetch article from backend
                        $.ajax({
                            url: '/news/article',
                            type: 'GET',
                            data: {
                                provider: provider,
                                articleId: articleId
                            },
                            dataType: 'json',
                            success: function(data) {
                                var articleText = data.articleText || '';
                                var cleanedText = cleanNewsArticleText(articleText);

                                var escaped = $('<div/>').text(cleanedText).html();
                                var displayHtml = '<pre style="font-size:14px;color:#1f2328;line-height:1.6;white-space:pre-wrap;word-wrap:break-word;font-family:\\'Segoe UI\\', sans-serif;border:none;background:transparent;padding:0;margin:0;">' + escaped + '</pre>';

                                $('#newsArticleContent').html(displayHtml);
                            },
                            error: function(xhr) {
                                var errorMsg = 'Failed to load article.';
                                try {
                                    var resp = JSON.parse(xhr.responseText);
                                    if (resp.error) errorMsg = resp.error;
                                } catch(e) {}
                                $('#newsArticleContent').html('<div style="color:#d32f2f;font-size:14px;padding:10px;background:#ffebee;border-radius:4px;">' + errorMsg + '</div>');
                            }
                        });
                    }
'''

new_text = text[:start] + new_func + text[end_func:]
path.write_text(new_text, encoding='utf-8')
print('patched', path, 'from', start, 'to', end_func)
