from django.db import migrations


INTERESTS = [
    ('walking-hiking', 'Walking & hiking', 'Outdoors & nature'),
    ('biking', 'Biking', 'Outdoors & nature'),
    ('camping', 'Camping', 'Outdoors & nature'),
    ('water-activities', 'Water activities', 'Outdoors & nature'),
    ('gardening', 'Gardening', 'Outdoors & nature'),
    ('birding-wildlife', 'Birding & wildlife', 'Outdoors & nature'),
    ('fitness-workouts', 'Fitness & workouts', 'Sports & movement'),
    ('running', 'Running', 'Sports & movement'),
    ('team-sports', 'Team sports', 'Sports & movement'),
    ('racquet-sports', 'Racquet sports', 'Sports & movement'),
    ('yoga-mindfulness', 'Yoga & mindfulness', 'Sports & movement'),
    ('dancing', 'Dancing', 'Sports & movement'),
    ('board-card-games', 'Board & card games', 'Games & play'),
    ('tabletop-rpgs', 'Tabletop RPGs', 'Games & play'),
    ('video-games', 'Video games', 'Games & play'),
    ('puzzles-trivia', 'Puzzles & trivia', 'Games & play'),
    ('live-music', 'Live music', 'Arts & culture'),
    ('making-music', 'Making music', 'Arts & culture'),
    ('theater-comedy', 'Theater & comedy', 'Arts & culture'),
    ('movies', 'Movies', 'Arts & culture'),
    ('museums-galleries', 'Museums & galleries', 'Arts & culture'),
    ('books-writing', 'Books & writing', 'Arts & culture'),
    ('photography', 'Photography', 'Arts & culture'),
    ('arts-crafts', 'Arts & crafts', 'Arts & culture'),
    ('cooking-baking', 'Cooking & baking', 'Food & exploring'),
    ('dining-coffee', 'Dining & coffee', 'Food & exploring'),
    ('local-exploring', 'Local exploring', 'Food & exploring'),
    ('travel', 'Travel', 'Food & exploring'),
    ('technology-making', 'Technology & making', 'Learning & making'),
    ('science-nature', 'Science & nature', 'Learning & making'),
    ('languages', 'Languages', 'Learning & making'),
    ('classes-learning', 'Classes & learning', 'Learning & making'),
    ('diy-home-projects', 'DIY & home projects', 'Learning & making'),
    ('volunteering', 'Volunteering', 'Community & connection'),
    ('mutual-aid-helping', 'Mutual aid & helping', 'Community & connection'),
    ('mentoring', 'Mentoring', 'Community & connection'),
    ('pets-animals', 'Pets & animals', 'Community & connection'),
]


def seed_interests(apps, schema_editor):
    Interest = apps.get_model('social', 'Interest')
    for slug, name, section in INTERESTS:
        Interest.objects.using(schema_editor.connection.alias).get_or_create(
            slug=slug, defaults={'name': name, 'section': section})


class Migration(migrations.Migration):
    dependencies = [('social', '0007_interest_userprofile_interests_prompt_pending_and_more')]
    operations = [migrations.RunPython(seed_interests, migrations.RunPython.noop)]
