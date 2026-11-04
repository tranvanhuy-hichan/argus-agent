"""Danh muc dich vu MCP tu xa da kiem chung.

Moi muc da duoc thu bang chinh luong cua Argus (SDK MCP) tren dia chi that: `oauth` = lay duoc dia chi dang nhap (kham pha + dang ky client dong
thanh cong), `open` = ket noi khong can dang nhap va liet ke duoc cong cu, `token` = can token ca nhan (nha cung cap khong cho tu dang ky).
Cac dich vu thu nhung khong dung duoc (Slack, HubSpot, Box, Calendly, Gamma, Figma...) khong dua vao day.
"""

GROUPS = [
    {"id": "dev", "label": {"vi": "Lập trình và triển khai", "en": "Code and deployment"}},
    {"id": "data", "label": {"vi": "Dữ liệu và hạ tầng", "en": "Data and infrastructure"}},
    {"id": "search", "label": {"vi": "Tìm kiếm và tài liệu", "en": "Search and docs"}},
    {"id": "work", "label": {"vi": "Công việc và cộng tác", "en": "Work and collaboration"}},
    {"id": "design", "label": {"vi": "Thiết kế và website", "en": "Design and websites"}},
    {"id": "biz", "label": {"vi": "Kinh doanh và thanh toán", "en": "Business and payments"}},
]


def _s(id, name, url, group, auth, vi, en, color="6B7280", transport="http", **extra):
    return {"id": id, "name": name, "url": url, "group": group, "auth": auth, "transport": transport, "color": color, "desc": {"vi": vi, "en": en}, **extra}


GITHUB_TOKEN = {"header": "Authorization", "prefix": "Bearer ", "help_url": "https://github.com/settings/personal-access-tokens/new",
                "hint": {"vi": "Tạo một Personal Access Token trên GitHub (chỉ cấp quyền cần thiết) rồi dán vào đây.", "en": "Create a Personal Access Token on GitHub (grant only the permissions you need) and paste it here."}}

SERVICES = [
    # --- Lap trinh va trien khai
    _s("github", "GitHub", "https://api.githubcopilot.com/mcp/", "dev", "token", "Đọc repo, issue, pull request và Actions bằng token cá nhân.", "Read repos, issues, pull requests and Actions with a personal token.", "181717", token=GITHUB_TOKEN),
    _s("gitlab", "GitLab", "https://gitlab.com/api/v4/mcp", "dev", "oauth", "Xem project, issue và merge request trên GitLab.", "View projects, issues and merge requests on GitLab.", "FC6D26"),
    _s("vercel", "Vercel", "https://mcp.vercel.com", "dev", "oauth", "Xem project, deployment và log trên Vercel.", "Inspect projects, deployments and logs on Vercel.", "000000"),
    _s("netlify", "Netlify", "https://netlify-mcp.netlify.app/mcp", "dev", "oauth", "Quản lý site và deploy trên Netlify.", "Manage sites and deploys on Netlify.", "00C7B7"),
    _s("cloudflare-bindings", "Cloudflare Workers", "https://bindings.mcp.cloudflare.com/mcp", "dev", "oauth", "Quản lý Workers, KV, D1, R2 trên Cloudflare.", "Manage Workers, KV, D1 and R2 on Cloudflare.", "F38020"),
    _s("cloudflare-observability", "Cloudflare Observability", "https://observability.mcp.cloudflare.com/mcp", "dev", "oauth", "Xem log và số liệu của Workers trên Cloudflare.", "Read Workers logs and analytics on Cloudflare.", "F38020"),
    _s("cloudflare-docs", "Cloudflare Docs", "https://docs.mcp.cloudflare.com/mcp", "dev", "open", "Tra cứu tài liệu Cloudflare, không cần đăng nhập.", "Search the Cloudflare docs. No sign-in needed.", "F38020"),
    _s("sentry", "Sentry", "https://mcp.sentry.dev/mcp", "dev", "oauth", "Xem lỗi, issue và hiệu năng ứng dụng trong Sentry.", "Look at errors, issues and performance in Sentry.", "362D59"),
    _s("datadog", "Datadog", "https://mcp.datadoghq.com/api/unstable/mcp-server/mcp", "dev", "oauth", "Truy vấn log, metric và monitor trong Datadog.", "Query logs, metrics and monitors in Datadog.", "632CA6"),
    _s("jam", "Jam", "https://mcp.jam.dev/mcp", "dev", "oauth", "Đọc báo cáo lỗi kèm bản ghi màn hình từ Jam.", "Read bug reports with screen recordings from Jam.", "F2A93B"),
    _s("context7", "Context7", "https://mcp.context7.com/mcp", "dev", "open", "Tài liệu thư viện lập trình luôn mới nhất, không cần đăng nhập.", "Up-to-date library documentation. No sign-in needed.", "059669"),
    _s("deepwiki", "DeepWiki", "https://mcp.deepwiki.com/mcp", "dev", "open", "Hỏi đáp về mã nguồn các repo GitHub công khai.", "Ask questions about public GitHub repositories.", "2563EB"),
    _s("microsoft-learn", "Microsoft Learn", "https://learn.microsoft.com/api/mcp", "dev", "open", "Tra cứu tài liệu Microsoft và Azure, không cần đăng nhập.", "Search Microsoft and Azure docs. No sign-in needed.", "0078D4"),
    # --- Du lieu va ha tang
    _s("neon", "Neon", "https://mcp.neon.tech/mcp", "data", "oauth", "Quản lý project và chạy SQL trên Neon Postgres.", "Manage projects and run SQL on Neon Postgres.", "00E599"),
    _s("supabase", "Supabase", "https://mcp.supabase.com/mcp", "data", "oauth", "Quản lý project, bảng và truy vấn trên Supabase.", "Manage projects, tables and queries on Supabase.", "3FCF8E"),
    _s("posthog", "PostHog", "https://mcp.posthog.com/mcp", "data", "oauth", "Xem phân tích sản phẩm, feature flag và thí nghiệm.", "Browse product analytics, feature flags and experiments.", "F9BD2B"),
    _s("apify", "Apify", "https://mcp.apify.com", "data", "oauth", "Chạy các Actor để thu thập dữ liệu web.", "Run Actors to scrape and collect web data.", "97D700"),
    _s("huggingface", "Hugging Face", "https://huggingface.co/mcp", "data", "open", "Tìm model, dataset và Space trên Hugging Face.", "Search models, datasets and Spaces on Hugging Face.", "FFD21E"),
    _s("alphavantage", "Alpha Vantage", "https://mcp.alphavantage.co/mcp", "data", "oauth", "Dữ liệu chứng khoán, ngoại hối và tiền mã hóa.", "Stock, forex and crypto market data.", "1A56DB"),
    # --- Tim kiem va tai lieu
    _s("exa", "Exa", "https://mcp.exa.ai/mcp", "search", "open", "Tìm kiếm web bằng AI, không cần đăng nhập.", "AI-powered web search. No sign-in needed.", "1F40ED"),
    _s("firecrawl", "Firecrawl", "https://mcp.firecrawl.dev/mcp", "search", "open", "Đọc và thu thập nội dung trang web thành văn bản sạch.", "Read and crawl web pages into clean text.", "FF6B35"),
    _s("tavily", "Tavily", "https://mcp.tavily.com/mcp", "search", "oauth", "Tìm kiếm web được tối ưu cho agent.", "Web search tuned for agents.", "5B6CFF"),
    # --- Cong viec va cong tac
    _s("notion", "Notion", "https://mcp.notion.com/mcp", "work", "oauth", "Đọc và ghi trang, cơ sở dữ liệu trong Notion.", "Read and write pages and databases in Notion.", "000000"),
    _s("linear", "Linear", "https://mcp.linear.app/mcp", "work", "oauth", "Xem và tạo issue, project trong Linear.", "View and create issues and projects in Linear.", "5E6AD2"),
    _s("asana", "Asana", "https://mcp.asana.com/v2/mcp", "work", "oauth", "Quản lý công việc và dự án trong Asana.", "Manage tasks and projects in Asana.", "F06A6A"),
    _s("atlassian", "Atlassian", "https://mcp.atlassian.com/v1/mcp", "work", "oauth", "Jira và Confluence: tìm, đọc, tạo issue và trang.", "Jira and Confluence: search, read and create issues and pages.", "0052CC"),
    _s("clickup", "ClickUp", "https://mcp.clickup.com/mcp", "work", "oauth", "Quản lý task, danh sách và tài liệu trong ClickUp.", "Manage tasks, lists and docs in ClickUp.", "7B68EE"),
    _s("monday", "monday.com", "https://mcp.monday.com/mcp", "work", "oauth", "Quản lý bảng và mục công việc trên monday.com.", "Manage boards and items on monday.com.", "FF3D57"),
    _s("airtable", "Airtable", "https://mcp.airtable.com/mcp", "work", "oauth", "Đọc và ghi bản ghi trong các base Airtable.", "Read and write records in Airtable bases.", "18BFFF"),
    _s("todoist", "Todoist", "https://ai.todoist.net/mcp", "work", "oauth", "Quản lý việc cần làm trong Todoist.", "Manage your to-dos in Todoist.", "E44332"),
    _s("miro", "Miro", "https://mcp.miro.com", "work", "oauth", "Đọc và tạo nội dung trên bảng Miro.", "Read and create content on Miro boards.", "FFD02F"),
    _s("fireflies", "Fireflies", "https://api.fireflies.ai/mcp", "work", "oauth", "Tìm trong bản ghi và tóm tắt các cuộc họp.", "Search meeting transcripts and summaries.", "7C3AED"),
    _s("granola", "Granola", "https://mcp.granola.ai/mcp", "work", "oauth", "Truy cập ghi chú cuộc họp trong Granola.", "Access meeting notes in Granola.", "5CAB2A"),
    _s("zapier", "Zapier", "https://mcp.zapier.com/api/mcp/mcp", "work", "oauth", "Kích hoạt các hành động trong hàng nghìn ứng dụng qua Zapier.", "Trigger actions across thousands of apps through Zapier.", "FF4F00"),
    # --- Thiet ke va website
    _s("canva", "Canva", "https://mcp.canva.com/mcp", "design", "oauth", "Tìm, đọc và chỉnh thiết kế trong Canva.", "Find, read and edit designs in Canva.", "00C4CC"),
    _s("webflow", "Webflow", "https://mcp.webflow.com/mcp", "design", "oauth", "Quản lý site, trang và CMS của Webflow.", "Manage Webflow sites, pages and CMS.", "146EF5"),
    _s("wix", "Wix", "https://mcp.wix.com/mcp", "design", "oauth", "Quản lý site và cửa hàng trên Wix.", "Manage sites and stores on Wix.", "0C6EFC"),
    # --- Kinh doanh va thanh toan
    _s("stripe", "Stripe", "https://mcp.stripe.com", "biz", "oauth", "Xem khách hàng, thanh toán và hóa đơn trên Stripe.", "View customers, payments and invoices on Stripe.", "635BFF"),
    _s("paypal", "PayPal", "https://mcp.paypal.com/mcp", "biz", "oauth", "Quản lý giao dịch và hóa đơn trên PayPal.", "Manage transactions and invoices on PayPal.", "003087"),
    _s("square", "Square", "https://mcp.squareup.com/sse", "biz", "oauth", "Quản lý bán hàng, khách hàng và kho trên Square.", "Manage sales, customers and inventory on Square.", "3E4348", transport="sse"),
    _s("intercom", "Intercom", "https://mcp.intercom.com/mcp", "biz", "oauth", "Xem hội thoại và liên hệ khách hàng trong Intercom.", "View conversations and contacts in Intercom.", "6AFDEF"),
    _s("ramp", "Ramp", "https://mcp.ramp.com/mcp", "biz", "oauth", "Xem chi tiêu, thẻ và hóa đơn trên Ramp.", "View spend, cards and bills on Ramp.", "F4D03F"),
]


def catalog() -> dict:
    return {"groups": GROUPS, "services": SERVICES}
