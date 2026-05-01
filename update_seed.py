import re

with open("apps/content/management/commands/seed_content.py", "r") as f:
    content = f.read()

# Add new models to imports
content = content.replace(
    "from apps.content.models import (",
    "from django.contrib.auth import get_user_model\nUser = get_user_model()\n\nfrom apps.content.models import (\n    BreathworkExercise, AmbientSound, SearchConfig,"
)

# Add to flush
content = content.replace(
    "UserDailyStat, UserPlanItem]",
    "UserDailyStat, UserPlanItem, BreathworkExercise, AmbientSound, SearchConfig]"
)

# Add function calls to handle
content = content.replace(
    "self._seed_daily_tips()",
    "self._seed_daily_tips()\n        self._seed_breathwork()\n        self._seed_ambient_sounds()\n        self._seed_search_config()\n        self._seed_user_data()"
)

# Add the new seed methods at the end
new_methods = """
    # ── Breathwork Exercises ────────────────────────────────────────
    def _seed_breathwork(self):
        data = [
            ("Awake", "6-0-2-0", "1 - 3 min", "#FFB300", "WbSunny"),
            ("Deep Calm", "4-7-8-0", "3 - 5 min", "#4A7C59", "NightlightRound"),
            ("Box Breathing", "4-4-4-4", "2 - 5 min", "#5C6BC0", "CropSquare"),
            ("Energy Boost", "2-0-2-0", "1 - 2 min", "#EF5350", "Bolt"),
            ("Nadi Shodhana", "4-4-4-4", "5 - 10 min", "#26A69A", "Air"),
            ("Ujjayi Breath", "5-0-5-0", "3 - 5 min", "#8BC34A", "Waves"),
            ("Kapalbhati", "1-0-1-0", "1 - 3 min", "#FF7043", "LocalFireDepartment"),
            ("Bhramari", "4-0-6-0", "3 - 5 min", "#AB47BC", "Hearing"),
        ]
        objs = []
        for i, (title, pattern, duration, color, icon) in enumerate(data):
            objs.append(BreathworkExercise(
                title=title, pattern=pattern, duration=duration,
                color_hex=color, icon_name=icon, order=i
            ))
        BreathworkExercise.objects.bulk_create(objs, ignore_conflicts=True)
        self.stdout.write(f"  ✓ {len(objs)} Breathwork Exercises")

    # ── Ambient Sounds ──────────────────────────────────────────────
    def _seed_ambient_sounds(self):
        data = [
            ("Rain", "🌧️", "#5C6BC0"),
            ("Ocean", "🌊", "#29B6F6"),
            ("Forest", "🌲", "#4A7C59"),
            ("Fire", "🔥", "#EF5350"),
            ("Wind", "🌬️", "#B0BEC5"),
            ("Thunder", "⛈️", "#455A64"),
            ("Birds", "🐦", "#8BC34A"),
            ("Night", "🦉", "#1A237E"),
            ("River", "🏞️", "#00897B"),
            ("White Noise", "📻", "#9E9E9E"),
        ]
        objs = []
        for i, (name, emoji, color) in enumerate(data):
            objs.append(AmbientSound(name=name, emoji=emoji, color_hex=color, order=i))
        AmbientSound.objects.bulk_create(objs, ignore_conflicts=True)
        self.stdout.write(f"  ✓ {len(objs)} Ambient Sounds")

    # ── Search Config ───────────────────────────────────────────────
    def _seed_search_config(self):
        config = SearchConfig(
            popular_searches=[
                "Pranayama techniques", "High protein Indian meals",
                "Morning yoga routine", "Calorie deficit recipes",
                "Meditation for sleep", "Ayurvedic detox",
                "HIIT for beginners", "Sattvic diet plan",
            ],
            filter_chips=["All", "Yoga", "Nutrition", "Meditation", "Recipes", "Fitness", "Sleep"]
        )
        config.save()
        self.stdout.write("  ✓ Search Config")

    # ── User Data ───────────────────────────────────────────────────
    def _seed_user_data(self):
        import random
        from datetime import date, timedelta, time
        users = User.objects.all()
        if not users.exists():
            self.stdout.write("  ⚠ No users found. Skipping user data seeding.")
            return

        today = date.today()
        stat_objs = []
        plan_objs = []
        
        sessions = list(Session.objects.all())
        
        for user in users:
            # 14 days of stats
            for i in range(14):
                d = today - timedelta(days=i)
                stat_objs.append(UserDailyStat(
                    user=user, date=d,
                    calories_consumed=random.randint(1200, 2500),
                    calories_burned=random.randint(300, 800),
                    water_glasses=random.randint(2, 8),
                    water_goal=8,
                    heart_rate_avg=random.randint(60, 85),
                    steps=random.randint(3000, 12000),
                    sleep_hours=round(random.uniform(5.5, 8.5), 1),
                    streak_days=14 - i,
                    practice_minutes=random.randint(0, 60)
                ))
            
            # Today's plan
            times = [time(7, 0), time(12, 30), time(18, 0), time(21, 30)]
            titles = ["Morning Yoga", "Healthy Lunch", "Evening Run", "Sleep Meditation"]
            for i, t in enumerate(times):
                plan_objs.append(UserPlanItem(
                    user=user, date=today, time=t,
                    title=titles[i], subtitle=f"Part {i+1} of your day",
                    description="A structured part of your daily routine.",
                    tips=["Stay hydrated", "Breathe deeply"],
                    icon_name="SelfImprovement", color_hex="#4A7C59",
                    is_done=(i < 2), order=i,
                    session=random.choice(sessions) if sessions else None
                ))

        UserDailyStat.objects.bulk_create(stat_objs, ignore_conflicts=True)
        UserPlanItem.objects.bulk_create(plan_objs, ignore_conflicts=True)
        self.stdout.write(f"  ✓ {len(stat_objs)} User Daily Stats")
        self.stdout.write(f"  ✓ {len(plan_objs)} User Plan Items")
"""
content += new_methods

with open("apps/content/management/commands/seed_content.py", "w") as f:
    f.write(content)
