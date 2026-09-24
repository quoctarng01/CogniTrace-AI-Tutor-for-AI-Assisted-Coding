# Mẫu Đăng Ký Đề Tài Luận Văn — Bản Song Ngữ / Thesis Registration Form — Bilingual Draft

> **Bản nội bộ.** File này chứa nội dung điền sẵn cho **Mẫu Đăng Ký Đề Tài Luận Văn** của Trường ĐH Quốc Tế - ĐHQG TPHCM. Bạn có thể chép vào form giấy hoặc điền trực tiếp vào form PDF. Tất cả các con số, giả thuyết, và khẳng định đều lấy từ [`THESIS-00-RESEARCH-QUESTIONS.md`](./THESIS-00-RESEARCH-QUESTIONS.md) và [`THESIS-00-ABSTRACT.md`](./THESIS-00-ABSTRACT.md).
>
> **Cách dùng:** mở file này trong Cursor, điền các trường `[STUDENT_*]`, sau đó chép vào form giấy.

---

## 1. Thông tin sinh viên / Student Information

| Form field | Trường | English | Giá trị / Value |
|---|---|---|---|
| Họ và tên sinh viên | Student's name | | `[STUDENT_FULL_NAME]` |
| Mã số sinh viên | Student ID | | `[STUDENT_ID]` |
| Email | Email | | `[STUDENT_EMAIL]` |
| Số điện thoại | Phone | | `[STUDENT_PHONE]` |
| Ngành | Major | | Khoa học Máy tính / Computer Science *(đã điền sẵn trên form)* |
| Họ tên Giáo viên hướng dẫn 1 | Name of Supervisor 1 | | `[SUPERVISOR_FULL_NAME]` *(để trống cho đến khi GV ký)* |

---

## 2. Tên đề tài / Thesis Title

> **Tên đề tài đã nộp (đã đóng băng) / Submitted title (locked).**
>
> **English:** *A State-Grounded AI Tutor for Personalized Programming Support Using Large Language Models*
>
> **Tiếng Việt (dịch tương đương, không chính thức):** *Gia sư AI nền tảng trạng thái cho hỗ trợ lập trình cá nhân hóa sử dụng các mô hình ngôn ngữ lớn.*
>
> "State-grounded" trong đề tài này được hiểu theo hai trục đồng thời: **trạng thái thực thi** của chương trình (biến, nhánh, khung hàm — được chụp bởi execution fingerprints) và **trạng thái nhận thức** của người học (mức thành thạo, tải nhận thức, lịch sử hiểu sai). Việc kết hợp hai tín hiệu neo này trong một vòng lặp gia sư duy nhất là đóng góp trung tâm.

**Ghi chú cho giáo viên hướng dẫn / Notes for supervisor:**

- Tên đề tài đã nộp và không thể thay đổi sau khi form được ký. Mọi tài liệu trong repo này (abstract, contributions, README, slide deck) được căn chỉnh với cách diễn giải "state-grounded" hai trục nêu trên.
- **Có thể kiểm chứng được** (falsifiable): luận văn có thể được bảo vệ hoặc bị bác bỏ tùy vào việc cơ chế neo kép (runtime + learner state) có thực sự cải thiện kết quả đo được hay không.
- Vị trí hóa công trình trong một lĩnh vực nghiên cứu đang hoạt động (grounded generation / LLM hallucination in education / learner modeling), nên được đọc là luận văn **nghiên cứu**, không phải đồ án sản phẩm.

### Tên thay thế đã cân nhắc trước khi nộp / Earlier title alternatives (kept for record only)

1. *Hệ thống gia sư AI nền tảng dấu vết cho việc sửa lỗi Python trong CS1 / Trace-Grounded AI Tutoring for Python Debugging in CS1.*
2. *Neo giải thích của mô hình ngôn ngữ lớn vào trạng thái thực thi: Nghiên cứu trong chủ thể về CogniTrace so với chat LLM không nền tảng cho việc sửa lỗi CS1 / Grounding LLM Explanations in Runtime State: A Within-Subjects Study of CogniTrace vs. Ungrounded Chat for CS1 Debugging.*
3. *Vượt qua Python Tutor: Nghiên cứu thực nghiệm về giải thích AI nền tảng dấu vết cho việc hiểu sửa lỗi CS1 / Beyond Python Tutor: An Empirical Study of Trace-Grounded AI Explanations for CS1 Debugging Comprehension.*

**Tên đã đóng băng — không thay đổi sau khi form đã ký trừ khi giáo viên yêu cầu bằng văn bản.**

---

## 3. Mục tiêu và mục đích nghiên cứu / Thesis goals and objectives

> **Ba mục tiêu có thể đo lường được. Mỗi mục tiêu ánh xạ tới một chương luận văn cụ thể và một sản phẩm nghiên cứu đã được đăng ký trước.**
>
> **Three measurable goals. Each maps to a specific thesis chapter and to a pre-registered artifact.**

### Mục tiêu 1 — Mục tiêu thực nghiệm (mục tiêu chính, mang tính quyết định) / Goal 1 — Empirical (the primary, load-bearing goal)

**Tiếng Việt:**
*Lượng hóa việc liệu gia sư AI nền tảng trạng thái của CogniTrace — mỗi prompt được điều kiện hóa đồng thời trên trạng thái thực thi của mã sinh viên (neo dấu vết) và trạng thái nhận thức của người học (mức thành thạo + tải nhận thức + lịch sử hiểu sai) — có cải thiện độ chính xác sửa lỗi trong tác vụ chuyển đổi (transfer-task) cho sinh viên CS1 so với (a) chỉ dùng Python Tutor, và (b) Python Tutor kết hợp với chat LLM không nền tảng hay không.*

**English:**
*Quantify whether CogniTrace's state-grounded AI tutoring — every prompt conditioned on both the runtime state of the student's code (trace grounding) and the cognitive state of the learner (mastery + load + misconception history) — improves transfer-task debugging accuracy for CS1 students compared to (a) Python Tutor alone and (b) Python Tutor + ungrounded LLM chat.*

- **Giả thuyết chính đã đăng ký trước H1** *(xem `docs/THESIS-00-RESEARCH-QUESTIONS.md` §1).*
- **Hiệu ứng dự đoán / Predicted effect:** **≥ +20 điểm phần trăm** cải thiện tuyệt đối trên transfer-task accuracy so với nhóm chứng LLM không nền tảng; **Cohen's d ≥ 0.6**; **α = 0.05**, hiệu chỉnh Bonferroni cho ba so sánh cặp.
- **Mẫu / Sample:** **N = 24** sinh viên năm nhất ngành CS, **trong chủ thể (within-subjects)**, cân bằng (Latin square).
- **Kết quả chính / Primary outcome:** bug-identification accuracy và time-to-fix trên bộ 6 bug, cộng transfer-task accuracy trên mã mới dùng cùng khái niệm.
- **Kết quả phụ / Secondary outcomes:** pre/post quiz delta (Cronbach's α ≥ 0.7), System Usability Scale, phỏng vấn bán cấu trúc tùy chọn (n = 10).
- **Phân tách đóng góp (dự kiến) / Decomposition analysis (planned):** tách riêng đóng góp của trục runtime-state (CogniTrace bật neo runtime, tắt neo learner) và đóng góp của trục learner-state (ngược lại) để hỗ trợ khẳng định hai trục trong tên đề tài đã nộp.

**Nếu GVHD hỏi "tại sao within-subjects?" / If supervisor asks "why within-subjects?":**
→ Tăng power thống kê cho mẫu nhỏ tại một trường. N=24 với d ≥ 0.6 đạt power ≈ 0.85 với paired t-test.

### Mục tiêu 2 — Mục tiêu hệ thống / Goal 2 — System

**Tiếng Việt:**
*Xây dựng nền tảng theo dõi Python an toàn, có thể triển khai trong sản xuất, kết hợp (1) sinh sinh tăng cường truy xuất neo trạng thái thực thi (dấu vết → ngữ cảnh prompt cho LLM), (2) xây dựng prompt có neo trạng thái người học (tải nhận thức + mức thành thạo + lịch sử hiểu sai được tiêm vào mỗi prompt), (3) các điểm kiểm tra gợi nhớ chủ động được tạo bởi LLM tại các nhánh điều khiển, và (4) lặp lại theo khoảng cách thích ứng theo khóa là các thẻ khái niệm xuất phát từ dấu vết.*

**English:**
*Deliver a secure, production-deployable Python tracing platform that combines (1) runtime-state-grounded retrieval-augmented generation (trace → LLM prompt context), (2) learner-state-grounded prompt construction (load + mastery + misconception history injected into every prompt), (3) LLM-generated active-recall checkpoints at control-flow branches, and (4) adaptive spaced repetition keyed to trace-derived concept tags.*

- Nền tảng là **CogniTrace**, đã được hiện thực tại repository này.
- Tài liệu thiết kế kỹ thuật: `docs/ARCHITECTURE.md` và `README.engineering.md`.
- Mô hình sandbox bảo mật hai lớp (xác thực AST + cô lập subprocess với `setrlimit`, danh sách cấm cho `match/case`, truy cập dunder, generator DoS): xem `docs/SECURITY-SANDBOX.md`.
- 365+ bài kiểm thử backend (đã xác minh), 100% phủ trên `tracer/`, ≥ 25% phủ tổng thể với cổng kiểm soát trong CI. Frontend có Vitest + Playwright E2E.
- Các sản phẩm cho môi trường production: Docker Compose, GitHub Actions CI với ngưỡng phủ, script backup DB (`scripts/backup_db.sh`), kiểm thử tải (`scripts/load_test_traces.py`), pre-commit hooks, cache LLM địa chỉ nội dung, cuộn số liệu LLM hàng ngày.

**Đây là mục tiêu hệ thống:** có thể hoàn thành độc lập với việc nghiên cứu thực nghiệm có tìm thấy hiệu ứng có ý nghĩa hay không.

### Mục tiêu 3 — Mục tiêu phương pháp luận / Goal 3 — Methodological

**Tiếng Việt:**
*Đăng ký trước toàn bộ thiết kế nghiên cứu (giả thuyết, công cụ đo, mẫu, pipeline phân tích) trước khi bắt đầu thu thập dữ liệu, và vận hành pipeline đo lường có khả năng tái sản xuất xuyên suốt quá trình.*

**English:**
*Pre-register the full study design (hypotheses, instruments, sample, analysis pipeline) before data collection begins, and operate a reproducible measurement pipeline throughout.*

- Bản đăng ký trước: `docs/THESIS-00-RESEARCH-QUESTIONS.md`.
- Mọi sai lệch được ghi nhận minh bạch trong `docs/THESIS-DEVIATIONS.md` nếu xảy ra sau đăng ký.
- Bề mặt đo lường (LLM call metrics, cuộn hàng ngày, danh mục khái niệm, hàng đợi rà soát giải thích) được tài liệu hóa tại `docs/MEASUREMENT.md`.
- Khả năng tái sản xuất: dữ liệu thô, script phân tích, và đầu ra pipeline phân tích được đưa vào phụ lục luận văn; pipeline phân tích chạy không sửa đổi trên dữ liệu thô.

Nếu không có đăng ký trước khi thu thập dữ liệu, khẳng định thực nghiệm sẽ bị suy yếu khi xét duyệt. Mục tiêu phương pháp luận đảm bảo điều này không xảy ra.

---

## 4. Yêu cầu / Requirements

> **Những gì luận văn cần để có thể khả thi. Người nộp cam kết có thể đạt được; giáo viên hướng dẫn xác nhận là hợp lý.**

### Yêu cầu kỹ thuật (đa số đã sẵn sàng) / Technical requirements

| # | Yêu cầu / Requirement | Trạng thái / Status | Người chịu trách nhiệm / Owner |
|---|---|---|---|
| 1 | Python 3.11+, FastAPI, Next.js 15 / React 19 / TypeScript, Supabase (Postgres + Auth), Redis cho rate limiting phân tán | ✅ Đã xây | Sinh viên |
| 2 | Tối thiểu hai nhà cung cấp LLM: **Ollama Cloud** (miễn phí, chính) và **GitHub Models** (PAT, dự phòng) | ✅ Đã nối; cần khóa ở runtime | Sinh viên |
| 3 | Database với bốn bảng phục vụ nghiên cứu: `traces`, `review_cards`, `explanations`, `llm_call_metrics`. Schema migrations V010–V013 đã có trong `backend/migrations/`. | ✅ Đã giao | Sinh viên |
| 4 | Sandbox bảo mật chấp nhận được để thực thi mã Python do sinh viên nộp: mô hình hai lớp (xác thực AST + cô lập subprocess với giới hạn tài nguyên, danh sách cấm cho `match/case`, truy cập dunder, generator DoS). | ✅ Đã hiện thực; tài liệu tại `docs/SECURITY-SANDBOX.md` | Sinh viên |

### Yêu cầu về dữ liệu và người tham gia / Data and participants

| # | Yêu cầu / Requirement | Trạng thái / Status | Người chịu trách nhiệm / Owner |
|---|---|---|---|
| 5 | Phê duyệt của Hội đồng Đạo đức hoặc phòng ban tương đương (hoặc miễn trừ chính thức theo Danh mục 1 cho nghiên cứu giáo dục) | ⏳ Sẽ nộp | Sinh viên, có chữ ký của GVHD |
| 6 | 24 sinh viên CS1 làm người tham gia (hoặc 5–8 cho pilot nếu giáo viên thu hẹp quy mô) | ⏳ Sẽ tuyển | Sinh viên |
| 7 | Phiên làm việc 30 phút với mỗi người tham gia, có phỏng vấn 10 phút tùy chọn cho n = 10 | ⏳ Sẽ lên lịch | Sinh viên |
| 8 | Ẩn danh hóa: mã nghiên cứu thay cho mã người dùng; bản ghi phỏng vấn bị xóa sau khi phiên âm | ✅ Đã thiết kế trong protocol; chờ phê duyệt đạo đức | Sinh viên |

### Yêu cầu về thời gian (cửa sổ nộp 8 tuần) / Timeline

| Tuần / Week | Sản phẩm / Deliverable |
|---|---|
| **W1** | Đóng băng đăng ký trước; môi trường dev chạy đầu cuối (khóa LLM hoạt động); flow consent người tham gia hoạt động; instrumentation thời gian phiên được thêm vào |
| **W2** | Tuyển người tham gia |
| **W3** | Chạy các phiên pilot |
| **W4** | Đợt rà soát neo thủ công trên một mẫu giải thích |
| **W5** | Notebook phân tích tạo ra p50/p95 latency, cache-hit rate, checkpoint accuracy, explanation grounding rate — trả lời RQ1–RQ4 |
| **W6** | Viết chương Methods + Results |
| **W7** | Thảo luận, giới hạn, GVHD review |
| **W8** | Polish cuối cùng và chuẩn bị bảo vệ |

Nếu GVHD có cửa sổ thời gian hẹp hơn, **RQ2 và RQ3 là exploratory và có thể cắt bỏ mà không làm mất hiệu lực của Mục tiêu 1.** Chỉ riêng Mục tiêu 1 đã đủ cho bảo vệ luận văn.

### Yêu cầu về tính toán / tài trợ / Compute / funding

- Không cần tài trợ tính toán bên ngoài cho pilot. Ollama Cloud miễn phí. GitHub Models miễn phí với PAT. Thực thi trace chạy trong container Docker với giới hạn tài nguyên cố định.
- Supabase tầng miễn phí hỗ trợ quy mô người tham gia pilot N=24.

### Rủi ro đã giảm thiểu / Open risks already mitigated

- `eval()` đã được loại bỏ khỏi tracer (`workstream 5 của hardening plan`); trace predicates giờ biên dịch thành lambda thông qua biến đổi AST. Xem `backend/tracer/tracer.py`.
- Quyền riêng tư khóa trace: namespace objects được gỡ bỏ `os` / `sys` trước khi serialize. Xem `docs/SECURITY-SANDBOX.md` rủi ro dư #5.

---

## 5. Tóm tắt hai dòng giáo viên sẽ đọc đầu tiên / Two-line summary your supervisor will read first

> **Tiếng Việt:** *Luận văn này điều tra việc liệu giải thích của mô hình ngôn ngữ lớn có neo trạng thái thực thi có cải thiện sự hiểu sửa lỗi CS1 so với chat LLM không nền tảng hay không. Hệ thống đã được xây (CogniTrace, trong repository này); phần việc còn lại là chạy nghiên cứu trong chủ thể đã đăng ký trước, tạo ra phép đo có khả năng phản biện về hiệu ứng của trace-grounding, và báo cáo kết quả minh bạch trong luận văn 6 chương.*
>
> **English:** *This thesis investigates whether runtime-state-grounded LLM explanations improve CS1 debugging comprehension compared to ungrounded LLM chat. The system is built (CogniTrace, in this repository); the work remaining is to run the pre-registered within-subjects study, produce a defensible measurement of the trace-grounding effect, and report results transparently in a 6-chapter thesis.*

---

## 6. Chữ ký / Signatures (ký tay trên form giấy / sign by hand on the printed form)

| Người ký / Signer | Họ tên / Name | Chữ ký / Signature | Ngày / Date |
|---|---|---|---|
| Sinh viên / Student | `[STUDENT_FULL_NAME]` | _________________ | _____________ |
| GVHD 1 / Supervisor 1 | `[SUPERVISOR_FULL_NAME]` | _________________ | _____________ |

> Sau khi cả hai bên ký, nộp form cho **Trợ lý học thuật bậc đại học của Khoa** theo hướng dẫn trên form.

---

## 7. Điều nói trong cuộc hẹn với giáo viên (30 giây) / What to say at the supervisor meeting (30-second pitch)

> **Tiếng Việt:**
> *"Phản hồi của thầy/cô về phiên bản 1 là 'không có gì đặc biệt, không có gì mới'. Em đã tái định hướng công trình thành luận văn nghiên cứu: cùng một hệ thống, nhưng có giả thuyết đăng ký trước (RQ1), kết quả chính rõ ràng (transfer-task accuracy), ngưỡng kích thước hiệu ứng (d ≥ 0.6), và thiết kế trong chủ thể với ba điều kiện. Phần kỹ thuật đã xong. Phần việc còn lại là nghiên cứu thực nghiệm trong 8 tuần. Em mong thầy/cô ký form đăng ký này để em tiếp tục."*
>
> **English:**
> *"The supervisor feedback on v1 was 'nothing special, nothing new.' I've reframed the work as a research thesis: the same system, but with a pre-registered hypothesis (RQ1), a clear primary outcome (transfer-task accuracy), an effect-size threshold (d ≥ 0.6), and a within-subjects design with three conditions. The engineering is done. What remains is the empirical study over 8 weeks. I'd like your sign-off on this registration form to proceed."*

---

## 8. Điều nói nếu giáo viên phản đối / What to do if the supervisor pushes back

| Phản đối / Pushback | Trả lời / Response |
|---|---|
| *"Tại sao research question? Đây là đồ án kỹ thuật." / "Why research questions? This is an engineering project."* | Form yêu cầu "goals and objectives". Của em được viết thành mục tiêu đo lường được với ngưỡng cấp giả thuyết. Sản phẩm đăng ký trước (`docs/THESIS-00-RESEARCH-QUESTIONS.md`) là sản phẩm biến kỹ thuật thành nghiên cứu. |
| *"Em không có N=24." / "You don't have N=24."* | Pilot là N=5–8 (khả thi trong 8 tuần). Luận văn được cấu trúc để pilot nhỏ nuôi nghiên cứu đầy đủ sau. RQ2/RQ3 có thể cắt. |
| *"Đóng góp chưa đủ mới." / "The contribution isn't novel enough."* | Đóng góp phương pháp luận (cache hit rate như proxy cho grounding reuse) cộng đóng góp sư phạm (sửa đổi SM-2 soft-fail) có thể bảo vệ độc lập. Ngay cả khi RQ1 là null, hai đóng góp đã đặt tên vẫn sống. Xem `docs/THESIS-02-CONTRIBUTIONS.md` §6. |
| *"Chỉ xây tính năng thôi." / "Just build a feature."* | Các tính năng đã xây (365+ tests, security hardening, LLM telemetry, v.v.). Luận văn là sản phẩm; các tính năng là bằng chứng. |
| *"Tôi không biết research question là gì sau khi đọc form." / "I don't know what the research question is even after reading the form."* | Hướng dẫn đến công thức một dòng tại §1 của `docs/THESIS-00-RESEARCH-QUESTIONS.md`: *"Trace-grounded LLM explanations improve debugging comprehension by ≥ 20 pp over ungrounded LLM chat."* |

---

## 9. Ánh xạ đến tài liệu hiện có / Where this draft maps to existing thesis artifacts

| Hàng form / Form row | Tài liệu / Artifact |
|---|---|
| Tên đề tài / Title | `docs/THESIS-00-ABSTRACT.md` §"Title" |
| Mục tiêu §1 / Goals §1 | `docs/THESIS-00-RESEARCH-QUESTIONS.md` §1 (H1), §3 (RQ1), §5 (Primary analysis) |
| Mục tiêu §2 / Goals §2 | `docs/ARCHITECTURE.md`, `README.engineering.md`, `docs/SECURITY-SANDBOX.md` |
| Mục tiêu §3 / Goals §3 | `docs/MEASUREMENT.md`, `docs/THESIS-00-RESEARCH-QUESTIONS.md` §7 |
| Yêu cầu / Requirements | `docs/THESIS-01-STUDY-PROTOCOL.md` + engineering README |

---

## 10. Phiên bản / Versioning

| Phiên bản / Version | Ngày / Date | Thay đổi / Change |
|---|---|---|
| 1.0 | 2026-09-23 | Bản song ngữ toàn form, dùng title (A). |
