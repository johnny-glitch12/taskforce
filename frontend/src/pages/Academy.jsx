import { GraduationCap, Play, Code2, BookOpen, Clock, Users, Star, Lock, ArrowRight } from "lucide-react";

const COURSES = [
  {
    id: 1,
    title: "Build Your First AI Agent",
    description: "Learn the fundamentals of autonomous agents from scratch. No ML experience required.",
    level: "Beginner",
    duration: "2h 30m",
    lessons: 12,
    students: 1847,
    rating: 4.9,
    tags: ["Python", "LLMs", "Prompting"],
    free: true,
  },
  {
    id: 2,
    title: "Prompt Engineering Masterclass",
    description: "Master the art of writing effective prompts that make agents reliable and safe.",
    level: "Intermediate",
    duration: "3h 15m",
    lessons: 18,
    students: 2340,
    rating: 4.8,
    tags: ["Prompt Design", "Safety", "Testing"],
    free: true,
  },
  {
    id: 3,
    title: "Agent Security & Trust Scoring",
    description: "Implement firewalls, sandboxing, and trust score systems for production agents.",
    level: "Advanced",
    duration: "4h 00m",
    lessons: 22,
    students: 983,
    rating: 4.9,
    tags: ["Security", "Firewalls", "Sandboxing"],
    free: false,
  },
  {
    id: 4,
    title: "Multi-Agent Orchestration",
    description: "Design systems where multiple agents collaborate, delegate, and verify each other's work.",
    level: "Advanced",
    duration: "5h 20m",
    lessons: 28,
    students: 671,
    rating: 4.7,
    tags: ["Architecture", "Workflows", "Scaling"],
    free: false,
  },
];

const LEVEL_COLORS = {
  Beginner: "text-emerald-400 bg-emerald-500/10",
  Intermediate: "text-amber-400 bg-amber-500/10",
  Advanced: "text-[#A78BFA] bg-[#8B5CF6]/10",
};

function CourseCard({ course }) {
  return (
    <div
      data-testid={`course-card-${course.id}`}
      className="rounded-2xl overflow-hidden transition-all duration-300 hover:shadow-lg group"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
      }}
    >
      {/* Video Placeholder */}
      <div className="relative h-44 overflow-hidden" style={{ background: 'var(--bg-secondary)' }}>
        <div className="absolute inset-0 flex items-center justify-center">
          <div
            className="w-14 h-14 rounded-full flex items-center justify-center backdrop-blur-sm transition-transform duration-300 group-hover:scale-110"
            style={{ background: 'rgba(139,92,246,0.15)', border: '1px solid rgba(139,92,246,0.3)' }}
          >
            <Play size={22} className="text-[#A78BFA] ml-0.5" fill="currentColor" />
          </div>
        </div>
        {/* Course number overlay */}
        <div className="absolute top-3 left-3 text-[10px] font-mono t-text-dim px-2 py-1 rounded-md" style={{ background: 'var(--bg-card)' }}>
          {String(course.id).padStart(2, '0')}
        </div>
        {!course.free && (
          <div className="absolute top-3 right-3 flex items-center gap-1 text-[10px] text-amber-400 bg-amber-500/10 px-2 py-1 rounded-md">
            <Lock size={10} /> Pro
          </div>
        )}
      </div>

      <div className="p-5">
        {/* Level + Duration */}
        <div className="flex items-center gap-2 mb-3">
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${LEVEL_COLORS[course.level]}`}>
            {course.level}
          </span>
          <span className="text-[11px] t-text-dim flex items-center gap-1">
            <Clock size={10} /> {course.duration}
          </span>
        </div>

        {/* Title */}
        <h3
          className="text-[15px] font-medium t-text leading-snug mb-2"
          style={{ fontFamily: "'Outfit', sans-serif" }}
        >
          {course.title}
        </h3>

        {/* Description */}
        <p className="text-[12px] t-text-mute leading-relaxed mb-4 line-clamp-2">
          {course.description}
        </p>

        {/* Tags */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          {course.tags.map((tag) => (
            <span key={tag} className="text-[10px] t-text-dim px-2 py-0.5 rounded-md" style={{ background: 'var(--bg-card-hover)' }}>
              {tag}
            </span>
          ))}
        </div>

        {/* Footer stats */}
        <div className="flex items-center justify-between pt-3" style={{ borderTop: '1px solid var(--border)' }}>
          <div className="flex items-center gap-3 text-[11px] t-text-dim">
            <span className="flex items-center gap-1"><BookOpen size={10} /> {course.lessons} lessons</span>
            <span className="flex items-center gap-1"><Users size={10} /> {course.students.toLocaleString()}</span>
          </div>
          <span className="flex items-center gap-1 text-[11px]">
            <Star size={10} className="fill-amber-400 text-amber-400" />
            <span className="t-text font-medium">{course.rating}</span>
          </span>
        </div>
      </div>
    </div>
  );
}

function CodePlayground() {
  return (
    <div
      data-testid="code-playground"
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <Code2 size={13} className="text-[#8B5CF6]" />
        <span className="text-[12px] t-text-sub font-medium">Interactive Playground</span>
        <span className="ml-auto text-[10px] t-text-dim">Coming Soon</span>
      </div>
      <div className="p-5 font-mono text-[12px] leading-relaxed" style={{ background: '#0d0d0f' }}>
        <div className="text-zinc-500"># Build your first agent</div>
        <div><span className="text-[#A78BFA]">from</span> <span className="text-emerald-400">nova</span> <span className="text-[#A78BFA]">import</span> <span className="text-white">Agent, Tool</span></div>
        <div className="mt-2"><span className="text-[#A78BFA]">agent</span> = <span className="text-emerald-400">Agent</span>(</div>
        <div className="pl-4"><span className="text-amber-300">name</span>=<span className="text-emerald-300">"my_first_agent"</span>,</div>
        <div className="pl-4"><span className="text-amber-300">model</span>=<span className="text-emerald-300">"gemini-2.5-flash"</span>,</div>
        <div className="pl-4"><span className="text-amber-300">tools</span>=[<span className="text-emerald-400">Tool</span>.<span className="text-white">web_search</span>()],</div>
        <div>)</div>
        <div className="mt-2"><span className="text-[#A78BFA]">result</span> = <span className="text-white">agent</span>.<span className="text-amber-300">run</span>(<span className="text-emerald-300">"Find latest AI news"</span>)</div>
        <div className="mt-1 text-zinc-500"># Output: {"headline": "..."}</div>
      </div>
    </div>
  );
}

export default function Academy() {
  return (
    <div data-testid="academy-page" className="min-h-[calc(100vh-60px)] px-6 lg:px-8 py-12 md:py-16 relative">
      <div className="absolute top-[10%] left-1/2 -translate-x-1/2 w-[350px] h-[350px] rounded-full bg-[#8B5CF6]/[0.05] blur-[100px] pointer-events-none t-orb" />

      <div className="max-w-5xl mx-auto relative">
        {/* Header */}
        <div className="text-center mb-14">
          <div className="inline-flex items-center gap-2 mb-6 px-4 py-1.5 rounded-full" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
            <GraduationCap size={13} className="text-[#8B5CF6]" />
            <span data-testid="academy-badge" className="text-[11px] tracking-[0.15em] t-text-sub">
              Free Education Platform
            </span>
          </div>

          <h1
            className="text-4xl sm:text-5xl lg:text-[4.25rem] font-bold tracking-[-0.03em] leading-[1.08] t-text mb-5"
            style={{ fontFamily: "'Outfit', sans-serif" }}
          >
            Nova <span className="text-gradient-purple">Academy</span>
          </h1>

          <p
            data-testid="academy-subtext"
            className="text-base md:text-lg t-text-sub max-w-md mx-auto leading-relaxed"
          >
            Master autonomous AI agents. From zero to production.
          </p>
        </div>

        {/* Course Grid */}
        <section className="mb-14">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold t-text" style={{ fontFamily: "'Outfit', sans-serif" }}>
              Featured Courses
            </h2>
            <span className="text-[12px] t-text-dim">{COURSES.length} courses</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {COURSES.map((course) => (
              <CourseCard key={course.id} course={course} />
            ))}
          </div>
        </section>

        {/* Interactive Playground */}
        <section className="mb-14">
          <h2 className="text-lg font-semibold t-text mb-6" style={{ fontFamily: "'Outfit', sans-serif" }}>
            Try It Live
          </h2>
          <CodePlayground />
        </section>

        {/* CTA */}
        <div
          className="text-center py-12 rounded-2xl"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
          <h3 className="text-xl font-semibold t-text mb-3" style={{ fontFamily: "'Outfit', sans-serif" }}>
            Ready to build your first agent?
          </h3>
          <p className="text-[14px] t-text-sub mb-6">
            Start with our free beginner course. No credit card required.
          </p>
          <button className="px-7 py-3 bg-[#8B5CF6] text-white text-[14px] font-medium rounded-full hover:bg-[#A78BFA] transition-all duration-300 shadow-[0_0_20px_rgba(139,92,246,0.25)] flex items-center gap-2 mx-auto">
            Start Learning <ArrowRight size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
