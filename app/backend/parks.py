"""Curated guide data for flagship national parks.

This powers the "Explore" experience: suggested trips (wired into the timeline
planner), things to do nearby, places to eat, and the practical logistics
campers actually ask about — where the good showers are, where to do laundry,
where to resupply, and whether your phone will work.

Curation notes
--------------
* This is editorial seed data, not live API data. Hours, prices, and even
  which campgrounds are reservable shift season to season — every park links
  back to its official page for confirmation.
* ``rec_gov_id`` is only filled in where we are confident of the facility ID
  (they appear in recreation.gov URLs). Where it is ``None`` the planner opens
  with the name pre-filled and the user completes the ID via search/manual
  entry — better than linking to the wrong facility.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class PlanTarget:
    """A facility a suggested trip books through the timeline planner."""

    name: str
    entity_type: str  # "campground" | "permit"
    rec_gov_id: Optional[str] = None
    note: str = ""


@dataclass
class Trip:
    title: str
    style: str  # "classic" | "backcountry" | "family" | "adventure"
    nights: int
    best_months: str
    summary: str
    itinerary: list[str] = field(default_factory=list)
    targets: list[PlanTarget] = field(default_factory=list)


@dataclass
class Activity:
    name: str
    kind: str  # "hike" | "scenic" | "water" | "wildlife" | "town" | "night"
    detail: str


@dataclass
class Eat:
    name: str
    where: str
    detail: str


@dataclass
class Amenities:
    showers: list[str] = field(default_factory=list)
    laundry: list[str] = field(default_factory=list)
    groceries: list[str] = field(default_factory=list)
    connectivity: str = ""
    heads_up: str = ""


@dataclass
class Park:
    slug: str
    name: str
    state: str
    established: str
    tagline: str
    description: str
    best_seasons: str
    crowd_tip: str
    official_url: str
    trips: list[Trip] = field(default_factory=list)
    activities: list[Activity] = field(default_factory=list)
    eats: list[Eat] = field(default_factory=list)
    amenities: Amenities = field(default_factory=Amenities)

    def summary(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "state": self.state,
            "established": self.established,
            "tagline": self.tagline,
            "trip_count": len(self.trips),
        }

    def full(self) -> dict:
        return asdict(self)


PARKS: tuple[Park, ...] = (
    # ------------------------------------------------------------------ #
    Park(
        slug="yosemite",
        name="Yosemite",
        state="California",
        established="1890",
        tagline="Granite cathedrals and waterfall spray",
        description=(
            "Glacier-carved valley walls, the tallest waterfall in North America, "
            "and the high country of Tuolumne Meadows. The hardest part is not the "
            "hiking — it is winning the reservation."
        ),
        best_seasons="May–June for waterfalls, September for calm; Tioga Road opens ~late May",
        crowd_tip="Arrive in the Valley before 8 AM or after 5 PM; midday gridlock is real.",
        official_url="https://www.nps.gov/yose/",
        trips=[
            Trip(
                title="Valley Floor Classic",
                style="classic",
                nights=3,
                best_months="May–Jun, Sep",
                summary=(
                    "Base camp in the heart of the Valley with walk-up access to the "
                    "Mist Trail, meadow loops, and El Capitan sunset watching."
                ),
                itinerary=[
                    "Day 1 — Arrive, bike the Valley Loop, sunset at El Capitan Meadow",
                    "Day 2 — Mist Trail to Vernal & Nevada Falls (start by 7 AM)",
                    "Day 3 — Glacier Point sunrise drive, afternoon at Cathedral Beach",
                ],
                targets=[
                    PlanTarget("Upper Pines", "campground", "232447", "Largest Valley campground; releases sell out in seconds"),
                    PlanTarget("Lower Pines", "campground", "232450", "Smaller, closer to the river"),
                    PlanTarget("North Pines", "campground", "232449", "Quietest of the three Pines"),
                ],
            ),
            Trip(
                title="Tuolumne High Country",
                style="backcountry",
                nights=2,
                best_months="Jul–Sep",
                summary=(
                    "Cooler air at 8,600 ft, domes and alpine meadows, and day hikes to "
                    "Cathedral Lakes and Lembert Dome without Valley crowds."
                ),
                itinerary=[
                    "Day 1 — Drive Tioga Road, short hike to Soda Springs",
                    "Day 2 — Cathedral Lakes (7 mi) or Gaylor Lakes at sunset",
                    "Day 3 — Lembert Dome sunrise scramble, out via Olmsted Point",
                ],
                targets=[
                    PlanTarget("Tuolumne Meadows", "campground", "232448", "Reopened after rehab — check current status"),
                ],
            ),
            Trip(
                title="Half Dome Summit Bid",
                style="adventure",
                nights=1,
                best_months="Jun–Sep (cables up)",
                summary=(
                    "The famous cables route: 16 miles, 4,800 ft of gain, and a lottery "
                    "permit. Pair the preseason lottery with a Valley campsite."
                ),
                itinerary=[
                    "March — Enter the preseason lottery (or try the 2-day-ahead daily draw)",
                    "Night before — Sleep low, pack gloves for the cables",
                    "Summit day — On trail by 5 AM, off the cables before afternoon clouds",
                ],
                targets=[
                    PlanTarget("Half Dome Cables", "permit", "234652", "Preseason lottery in March + daily lottery in season"),
                ],
            ),
        ],
        activities=[
            Activity("Mist Trail", "hike", "The essential Yosemite hike — spray-soaked granite steps beside Vernal Falls. Go at dawn."),
            Activity("Glacier Point", "scenic", "The postcard view of Half Dome and the high country; drive or hike the Four Mile Trail."),
            Activity("Valley Loop by bike", "scenic", "12 flat miles under El Capitan — rentals at Curry Village, or bring your own."),
            Activity("El Capitan Meadow at dusk", "night", "Watch headlamps of climbers bivvying on the wall as the stars come out."),
            Activity("Tunnel View sunrise", "scenic", "The classic Ansel Adams frame, best in morning light with valley mist."),
        ],
        eats=[
            Eat("Curry Village Pizza Deck", "Yosemite Valley", "Post-hike institution — pizza and pitchers on the deck under Glacier Point."),
            Eat("The Ahwahnee Bar", "Yosemite Valley", "Grand-hotel atmosphere without the dining-room price; solid burgers and cocktails."),
            Eat("Degnan's Kitchen", "Yosemite Village", "Best quick sandwiches for the trail; grab breakfast before an early start."),
            Eat("Rush Creek Lodge restaurant", "Groveland (Hwy 120)", "Worth the stop on the way in or out the west entrance."),
        ],
        amenities=Amenities(
            showers=[
                "Curry Village shower house — open to all visitors for a small fee, the go-to after the Mist Trail",
                "Housekeeping Camp showers (seasonal)",
            ],
            laundry=["Housekeeping Camp laundromat (seasonal) — the only laundry in the Valley"],
            groceries=["Village Store (surprisingly complete), Curry Village & Housekeeping camp stores for basics"],
            connectivity="Usable LTE near Yosemite Village/Curry Village; dead in most of the Valley's west end and Tuolumne.",
            heads_up="Bear boxes are mandatory — never leave food in your car overnight.",
        ),
    ),
    # ------------------------------------------------------------------ #
    Park(
        slug="zion",
        name="Zion",
        state="Utah",
        established="1919",
        tagline="Sandstone walls a half-mile high",
        description=(
            "A slot-canyon oasis where the hikes go either straight up the walls "
            "(Angels Landing) or straight up the river (The Narrows). Springdale "
            "sits at the gate with the best town amenities of any big park."
        ),
        best_seasons="April–May and September–October; summer is hot but the Narrows helps",
        crowd_tip="The canyon is shuttle-only most of the year — park in Springdale and walk in.",
        official_url="https://www.nps.gov/zion/",
        trips=[
            Trip(
                title="Canyon Classic",
                style="classic",
                nights=3,
                best_months="Apr–May, Sep–Oct",
                summary=(
                    "Camp at the mouth of the canyon within walking distance of the "
                    "shuttle, Springdale restaurants, and the Watchman's evening glow."
                ),
                itinerary=[
                    "Day 1 — Arrive, Pa'rus Trail stroll, sunset on the Watchman",
                    "Day 2 — Angels Landing (permit) or Scout Lookout, afternoon by the river",
                    "Day 3 — Bottom-up Narrows wade as far as Wall Street",
                ],
                targets=[
                    PlanTarget("Watchman Campground", "campground", "232445", "The reservable campground inside the park — book 6 months out"),
                    PlanTarget("Angels Landing Pilot Permit", "permit", None, "Seasonal + day-before lotteries; see the lottery browser"),
                ],
            ),
            Trip(
                title="Narrows Top-Down Overnight",
                style="backcountry",
                nights=1,
                best_months="Jun–Sep (flow-dependent)",
                summary=(
                    "16 miles through the full slot canyon with a night on a sandbar — "
                    "a wilderness permit and low river flow required."
                ),
                itinerary=[
                    "Permit — Calendar opens ~2 months ahead; watch flow rates (<120 cfs)",
                    "Day 1 — Chamberlain's Ranch to a numbered riverside camp",
                    "Day 2 — Wall Street and Big Springs down to the Temple of Sinawava",
                ],
                targets=[
                    PlanTarget("Zion Wilderness Permits (Narrows)", "permit", None, "Book on recreation.gov; canyon closes when flow spikes"),
                ],
            ),
        ],
        activities=[
            Activity("The Narrows (bottom-up)", "water", "Wade the Virgin River between thousand-foot walls; rent canyoneering boots in Springdale."),
            Activity("Angels Landing", "hike", "Chain-assisted ridge scramble — permit required via lottery since 2022."),
            Activity("Canyon Overlook Trail", "scenic", "One mile to a huge payoff at sunset, no shuttle needed (east side)."),
            Activity("Kolob Canyons", "scenic", "The park's quiet northwest corner — crimson finger canyons, 40 min away."),
            Activity("Springdale gallery stroll", "town", "Art galleries and outfitters line the shuttle route through town."),
        ],
        eats=[
            Eat("Oscar's Cafe", "Springdale", "Giant post-hike burritos and sweet-potato fries on a patio under the cliffs."),
            Eat("King's Landing Bistro", "Springdale", "The dressed-up dinner option with canyon views."),
            Eat("Deep Creek Coffee", "Springdale", "Early-opening coffee and burritos — perfect before a shuttle-line start."),
            Eat("Zion Canyon Brew Pub", "Springdale", "Beer garden right at the park's pedestrian entrance."),
        ],
        amenities=Amenities(
            showers=[
                "Zion Outfitter (at the park entrance) — pay showers steps from Watchman",
                "Most Springdale campgrounds sell shower access to non-guests",
            ],
            laundry=["Happy Camper Market laundromat in Springdale"],
            groceries=["Sol Foods Supermarket in Springdale — full grocery a short walk from the gate"],
            connectivity="Good signal in Springdale and south campgrounds; none in the upper canyon or Narrows.",
            heads_up="Watchman books out instantly for spring/fall — set your 6-month reminder.",
        ),
    ),
    # ------------------------------------------------------------------ #
    Park(
        slug="grand-canyon",
        name="Grand Canyon",
        state="Arizona",
        established="1919",
        tagline="A mile deep and two billion years down",
        description=(
            "The South Rim runs year-round with the classic viewpoints; the depths "
            "belong to those with a backcountry permit and an early alarm. Rim "
            "weather and inner-canyon weather are two different planets."
        ),
        best_seasons="March–May and September–November on the rims; inner canyon is brutal in summer",
        crowd_tip="Sunrise at Mather Point beats the midday crush by hours, not minutes.",
        official_url="https://www.nps.gov/grca/",
        trips=[
            Trip(
                title="South Rim Sampler",
                style="classic",
                nights=2,
                best_months="Mar–May, Sep–Nov",
                summary=(
                    "Camp in the ponderosa forest near the village, walk the Rim Trail, "
                    "and drop a mile below the rim on the South Kaibab."
                ),
                itinerary=[
                    "Day 1 — Rim Trail from Mather Point to Hopi Point for sunset",
                    "Day 2 — South Kaibab to Cedar Ridge at dawn (down 1.5 mi, back up before heat)",
                    "Day 3 — Desert View Drive out the east entrance, Watchtower stop",
                ],
                targets=[
                    PlanTarget("Mather Campground", "campground", None, "South Rim village campground on recreation.gov — 6-month window"),
                ],
            ),
            Trip(
                title="Rim to River Overnight",
                style="backcountry",
                nights=2,
                best_months="Oct–Apr",
                summary=(
                    "Down the South Kaibab, nights at Bright Angel campground by the "
                    "Colorado, back up the Bright Angel Trail. Permits are the crux."
                ),
                itinerary=[
                    "4 months ahead — Apply in the backcountry permit window",
                    "Day 1 — South Kaibab down (no water on trail — carry it all)",
                    "Day 2 — Layover: Phantom Ranch lemonade, Ribbon Falls side trip",
                    "Day 3 — Bright Angel up via Havasupai Gardens",
                ],
                targets=[
                    PlanTarget("Grand Canyon Backcountry Permit", "permit", None, "Corridor campgrounds; lottery-like demand — apply the first eligible day"),
                ],
            ),
        ],
        activities=[
            Activity("Rim Trail at dawn", "scenic", "13 shuttle-served miles — walk any stretch west of the village in morning light."),
            Activity("South Kaibab to Ooh Aah Point", "hike", "The best short taste of below-the-rim hiking; 1.8 mi round trip."),
            Activity("Desert View Watchtower", "scenic", "Mary Colter's 1932 tower with murals and a 100-mile view up the canyon."),
            Activity("Night skies program", "night", "A certified Dark Sky Park — ranger telescope sessions in summer."),
            Activity("Grand Canyon Railway", "town", "Vintage train from Williams — a fun car-free arrival with kids."),
        ],
        eats=[
            Eat("El Tovar Dining Room", "South Rim village", "The 1905 grand dame — book ahead, ask for a window table."),
            Eat("Bright Angel Bicycles Café", "Mather Point", "Espresso and breakfast wraps right where you watch the sunrise."),
            Eat("Fred Harvey Burger", "Bright Angel Lodge", "Reliable and unfussy after a big rim-trail day."),
            Eat("Plaza Bonita", "Tusayan", "The gateway town's go-to Mexican after a long drive in."),
        ],
        amenities=Amenities(
            showers=["Camper Services building next to Mather Campground — coin showers year-round"],
            laundry=["Same Camper Services building — laundromat beside the showers"],
            groceries=["Canyon Village Market — a genuinely full supermarket on the rim"],
            connectivity="Decent near the village, gone below the rim. Download maps first.",
            heads_up="Every year hikers underestimate the climb out — going down is optional, coming up is mandatory.",
        ),
    ),
    # ------------------------------------------------------------------ #
    Park(
        slug="yellowstone",
        name="Yellowstone",
        state="Wyoming",
        established="1872",
        tagline="The world's first national park, still steaming",
        description=(
            "Half the planet's geysers, a Serengeti of bison and wolves in Lamar "
            "Valley, and a canyon painted yellow and pink. Distances are huge — "
            "plan by region, not by park."
        ),
        best_seasons="May–June for wildlife and waterfalls; September for elk bugling and thin crowds",
        crowd_tip="Geyser basins are empty before 9 AM even in July. Wildlife jams peak midday.",
        official_url="https://www.nps.gov/yell/",
        trips=[
            Trip(
                title="Geyser Basin Base Camp",
                style="classic",
                nights=3,
                best_months="Jun–Sep",
                summary=(
                    "Stay on the west side loop for Old Faithful, Grand Prismatic, and "
                    "the Firehole River — the park's greatest-hits corridor."
                ),
                itinerary=[
                    "Day 1 — Old Faithful + Upper Geyser Basin boardwalks at dusk",
                    "Day 2 — Grand Prismatic overlook from Fairy Falls trail, Firehole swim",
                    "Day 3 — Norris Geyser Basin, Artists Paintpots on the way out",
                ],
                targets=[
                    PlanTarget("Madison Campground", "campground", None, "Central to the geyser basins — note some Yellowstone camps book via Xanterra, not recreation.gov"),
                ],
            ),
            Trip(
                title="Lamar Valley Wildlife Watch",
                style="family",
                nights=2,
                best_months="May–Jun, Sep",
                summary=(
                    "The 'American Serengeti': dawn wolf-watching, bison herds at "
                    "arm's length (stay 25 yards!), and the quiet northeast corner."
                ),
                itinerary=[
                    "Day 1 — Set up, evening drive through Lamar with binoculars",
                    "Day 2 — Dawn at Slough Creek pullouts with the wolf watchers",
                    "Day 3 — Trout Lake loop, Beartooth Highway detour if open",
                ],
                targets=[
                    PlanTarget("Slough Creek Campground", "campground", None, "Small and primitive — the wildlife-watcher's favorite"),
                    PlanTarget("Pebble Creek Campground", "campground", None, "Backup in the same valley"),
                ],
            ),
        ],
        activities=[
            Activity("Grand Prismatic Overlook", "scenic", "The aerial view of the rainbow spring, via a short spur off Fairy Falls trail."),
            Activity("Old Faithful at night", "night", "Catch an eruption by moonlight after the buses leave — check predicted times."),
            Activity("Artist Point", "scenic", "The canvas view of the Lower Falls and the yellow canyon walls."),
            Activity("Dawn in Lamar Valley", "wildlife", "Wolves, bison, pronghorn — bring a spotting scope or befriend someone who has one."),
            Activity("Boiling River legacy soak", "water", "Check current status — soak spots change with river conditions."),
        ],
        eats=[
            Eat("Old Faithful Inn Dining Room", "Old Faithful", "Eat under the massive 1904 log lobby at least once."),
            Eat("Canyon Eatery", "Canyon Village", "Best of the in-park fast-casual options."),
            Eat("Cooke City Bearclaw Bakery", "Cooke City, MT", "Pre-dawn pastries on the way into Lamar Valley."),
            Eat("Wonderland Cafe", "Gardiner, MT", "The north-gate town's proper sit-down dinner."),
        ],
        amenities=Amenities(
            showers=["Canyon, Grant Village & Fishing Bridge camper service buildings — pay showers", "Old Faithful Lodge (ask at desk)"],
            laundry=["Canyon, Grant Village & Fishing Bridge camper services have laundromats"],
            groceries=["Canyon & Old Faithful general stores; full grocery in West Yellowstone or Gardiner"],
            connectivity="Assume none outside the villages — and enjoy it. Download offline maps.",
            heads_up="Some campgrounds book through Yellowstone National Park Lodges (Xanterra) rather than recreation.gov — check each one.",
        ),
    ),
    # ------------------------------------------------------------------ #
    Park(
        slug="glacier",
        name="Glacier",
        state="Montana",
        established="1910",
        tagline="The Crown of the Continent",
        description=(
            "Knife-edge arêtes, turquoise lakes, and the Going-to-the-Sun Road — "
            "possibly America's best drive. Vehicle reservations and early snow "
            "make timing everything."
        ),
        best_seasons="Mid-July–September (Logan Pass typically opens ~mid-July)",
        crowd_tip="Sun Road vehicle reservations release in advance and day-of — know both windows.",
        official_url="https://www.nps.gov/glac/",
        trips=[
            Trip(
                title="Many Glacier Basecamp",
                style="classic",
                nights=3,
                best_months="Jul–Sep",
                summary=(
                    "The park's most spectacular valley: Grinnell Glacier, boat-assisted "
                    "hikes, and moose in Fishercap Lake at dusk."
                ),
                itinerary=[
                    "Day 1 — Arrive via Babb, evening at Fishercap Lake for moose",
                    "Day 2 — Grinnell Glacier (11 mi, or shave miles with the boat)",
                    "Day 3 — Ptarmigan Tunnel or Iceberg Lake, huckleberry stop in Babb",
                ],
                targets=[
                    PlanTarget("Many Glacier Campground", "campground", None, "Reservable in summer on recreation.gov — extremely competitive"),
                ],
            ),
            Trip(
                title="Going-to-the-Sun Traverse",
                style="adventure",
                nights=2,
                best_months="Jul–Sep",
                summary=(
                    "West side to east side over Logan Pass with a night near each end — "
                    "hit the Highline Trail from the top."
                ),
                itinerary=[
                    "Day 1 — Apgar/Avalanche Lake warm-up under the cedars",
                    "Day 2 — Drive the Sun Road early, Highline Trail from Logan Pass",
                    "Day 3 — St. Mary side: Sunrift Gorge, Wild Goose Island overlook",
                ],
                targets=[
                    PlanTarget("Apgar Campground", "campground", None, "West-side anchor near Lake McDonald"),
                    PlanTarget("St. Mary Campground", "campground", None, "East-side anchor with mountain sunrises"),
                ],
            ),
        ],
        activities=[
            Activity("Highline Trail", "hike", "Contour the Garden Wall from Logan Pass — the best mile-for-mile hike in the park."),
            Activity("Lake McDonald at sunset", "scenic", "Rainbow pebbles through glass-clear water at Apgar."),
            Activity("Historic boat tours", "water", "1920s wooden boats on Many Glacier and St. Mary lakes cut miles off big hikes."),
            Activity("Polebridge & Bowman Lake", "scenic", "Gravel-road side trip to the wild North Fork; go slow, bring huckleberry money."),
            Activity("Logan Pass goat watching", "wildlife", "Mountain goats and bighorns loiter around the visitor center meadows."),
        ],
        eats=[
            Eat("Polebridge Mercantile", "North Fork", "Legendary huckleberry bear claws from a century-old off-grid bakery."),
            Eat("Two Dog Flats Grill", "Rising Sun", "Solid east-side dinner with St. Mary Lake out the window."),
            Eat("Eddie's Café", "Apgar Village", "Breakfast institution steps from Lake McDonald."),
            Eat("Nell's at Two Medicine", "Two Medicine (store)", "Snack-bar simplicity in the park's quiet southeast corner."),
        ],
        amenities=Amenities(
            showers=["Many Glacier & Fish Creek campgrounds have shower buildings", "KOA West Glacier sells showers to travelers"],
            laundry=["West Glacier and St. Mary village laundromats (seasonal)"],
            groceries=["Apgar & St. Mary camp stores for basics; real groceries in Columbia Falls/Whitefish"],
            connectivity="West Glacier and St. Mary have signal; the interior and North Fork do not.",
            heads_up="Carry bear spray and know how to use it — this is serious grizzly country.",
        ),
    ),
    # ------------------------------------------------------------------ #
    Park(
        slug="grand-teton",
        name="Grand Teton",
        state="Wyoming",
        established="1929",
        tagline="No foothills — just teeth of granite",
        description=(
            "The Tetons rise 7,000 feet straight off the sagebrush flats, with a "
            "string of piedmont lakes at their feet and Jackson's food scene twenty "
            "minutes away. Pairs perfectly with Yellowstone next door."
        ),
        best_seasons="June–September; late September for golden aspens and bugling elk",
        crowd_tip="Jenny Lake parking fills by 8 AM — take the first boat across instead.",
        official_url="https://www.nps.gov/grte/",
        trips=[
            Trip(
                title="Lakes & Canyons Classic",
                style="classic",
                nights=3,
                best_months="Jun–Sep",
                summary=(
                    "Camp under the range, boat across Jenny Lake into Cascade Canyon, "
                    "and end days on a String Lake beach."
                ),
                itinerary=[
                    "Day 1 — Mormon Row sunrise (Moulton barns), float the Snake in the afternoon",
                    "Day 2 — Jenny Lake boat to Inspiration Point + Cascade Canyon",
                    "Day 3 — String/Leigh Lake paddle, Oxbow Bend for sunset moose",
                ],
                targets=[
                    PlanTarget("Jenny Lake Campground", "campground", None, "Tents-only and tiny — the park's hottest ticket"),
                    PlanTarget("Colter Bay Campground", "campground", None, "Big, forgiving fallback with full services"),
                ],
            ),
            Trip(
                title="Teton Crest Sampler",
                style="backcountry",
                nights=2,
                best_months="Aug–Sep",
                summary=(
                    "A taste of the famous crest: up Paintbrush Canyon, over the divide, "
                    "out Cascade — camping zones by permit."
                ),
                itinerary=[
                    "January — Apply when the advance permit window opens",
                    "Day 1 — Paintbrush Canyon to Holly Lake zone",
                    "Day 2 — Paintbrush Divide (ice axe early season), Lake Solitude, out Cascade",
                ],
                targets=[
                    PlanTarget("Grand Teton Backcountry Permit", "permit", None, "Advance window in early January on recreation.gov"),
                ],
            ),
        ],
        activities=[
            Activity("Snake River scenic float", "water", "Guided drift under the full range — eagles, otters, and zero rapids."),
            Activity("Mormon Row at dawn", "scenic", "The Moulton barns with alpenglow on the Grand — the iconic photo."),
            Activity("Oxbow Bend", "wildlife", "Moose and reflections at dawn and dusk, right off the highway."),
            Activity("Laurance Rockefeller Preserve", "hike", "Capped parking keeps Phelps Lake trails serene."),
            Activity("Jackson Town Square", "town", "Elk-antler arches, galleries, and the après scene 20 minutes south."),
        ],
        eats=[
            Eat("Dornan's Pizza Pasta Company", "Moose", "Deck pizza with the single best restaurant view of the range."),
            Eat("Persephone Bakery", "Jackson", "Morning pastries worth the town detour."),
            Eat("Snake River Brewing", "Jackson", "The classic post-hike brewpub."),
            Eat("Leek's Pizzeria", "Colter Bay area", "Marina-side slices on Jackson Lake."),
        ],
        amenities=Amenities(
            showers=["Colter Bay Village — showers at the launderette building, open to visitors", "Signal Mountain Lodge (ask at desk)"],
            laundry=["Colter Bay launderette — the park's full-service laundry stop"],
            groceries=["Dornan's in Moose & Colter Bay store; full supermarkets in Jackson"],
            connectivity="Good along the highway corridor and Jackson; patchy in the canyons.",
            heads_up="Jenny Lake campsites vanish the instant the window opens — have Colter Bay as plan B.",
        ),
    ),
    # ------------------------------------------------------------------ #
    Park(
        slug="joshua-tree",
        name="Joshua Tree",
        state="California",
        established="1994",
        tagline="Boulder gardens under desert stars",
        description=(
            "Two deserts meet in a surreal landscape of monzogranite piles and "
            "Dr. Seuss trees. World-class bouldering, legendary night skies, and a "
            "high-desert town scene along the northern boundary."
        ),
        best_seasons="October–April; spring for wildflowers. Summer is for dawn and night only",
        crowd_tip="Weekends from fall to spring fill every campground — go midweek or book the minute the window opens.",
        official_url="https://www.nps.gov/jotr/",
        trips=[
            Trip(
                title="Boulders & Stars Weekend",
                style="classic",
                nights=2,
                best_months="Oct–Apr",
                summary=(
                    "Camp inside the rock piles themselves, scramble at golden hour, "
                    "and stay up for a Milky Way you can read by."
                ),
                itinerary=[
                    "Day 1 — Hidden Valley loop, sunset at Keys View over the Salton Sea",
                    "Day 2 — Ryan Mountain at dawn, Barker Dam petroglyphs, night sky session",
                    "Day 3 — Cholla Cactus Garden sunrise on the drive out south",
                ],
                targets=[
                    PlanTarget("Jumbo Rocks Campground", "campground", None, "Sites tucked between the formations — the park's most atmospheric"),
                    PlanTarget("Indian Cove Campground", "campground", None, "North-side canyon of rock, closer to town showers"),
                ],
            ),
            Trip(
                title="Climber's Basecamp",
                style="adventure",
                nights=3,
                best_months="Nov–Mar",
                summary=(
                    "The winter trad-climbing mecca: thousands of routes, campfire "
                    "culture, and rest-day saloon burritos."
                ),
                itinerary=[
                    "Day 1 — Warm up at Quail Springs / Trashcan Rock",
                    "Day 2 — Hidden Valley classics; watch the sunset from Intersection Rock",
                    "Day 3 — Rest day: Pioneertown & Pappy's, Integratone sound bath if booked",
                ],
                targets=[
                    PlanTarget("Hidden Valley Campground", "campground", None, "First-come only — arrive Thursday morning for a weekend site"),
                ],
            ),
        ],
        activities=[
            Activity("Hidden Valley loop", "hike", "One flat mile through a rock-walled valley — the park's essence in 40 minutes."),
            Activity("Keys View", "scenic", "5,000 ft over the Coachella Valley to the Salton Sea; best at sunset."),
            Activity("Cholla Cactus Garden", "scenic", "Backlit at sunrise, the chollas glow like they're plugged in."),
            Activity("Stargazing anywhere", "night", "A Dark Sky Park — even the campground view is planetarium-grade."),
            Activity("Pioneertown", "town", "1940s movie-set town turned music venue 20 minutes north."),
        ],
        eats=[
            Eat("Pappy & Harriet's", "Pioneertown", "Desert-famous BBQ and live music — book dinner or eat at the bar."),
            Eat("Crossroads Cafe", "Joshua Tree town", "The climbers' breakfast-and-burger institution."),
            Eat("Natural Sisters Cafe", "Joshua Tree town", "Smoothies and big healthy wraps for the cooler."),
            Eat("La Copine", "Flamingo Heights", "Destination-worthy high-desert bistro (check days open)."),
        ],
        amenities=Amenities(
            showers=["None in the park — Coyote Corner in Joshua Tree town sells hot showers", "Joshua Tree Lake RV & Campground (day rate)"],
            laundry=["Laundromats along Hwy 62 in Yucca Valley and Twentynine Palms"],
            groceries=["Stater Bros. and Vons in Yucca Valley; Joshua Tree Health Foods in town"],
            connectivity="Decent along the north boundary towns, near-zero inside the park.",
            heads_up="No water anywhere in the park — bring 2+ gallons per person per day.",
        ),
    ),
    # ------------------------------------------------------------------ #
    Park(
        slug="acadia",
        name="Acadia",
        state="Maine",
        established="1919",
        tagline="Where granite mountains meet the Atlantic",
        description=(
            "Pink granite summits, spruce forests, carriage roads built for "
            "bicycles, and lobster piers in every direction. First sunrise in "
            "America from Cadillac Mountain (reservation required)."
        ),
        best_seasons="June–October; early October for foliage — book far ahead",
        crowd_tip="The Island Explorer shuttle is free and beats Ocean Drive parking roulette.",
        official_url="https://www.nps.gov/acad/",
        trips=[
            Trip(
                title="Island Classic",
                style="classic",
                nights=3,
                best_months="Jun–Oct",
                summary=(
                    "Camp on the quiet side of Mount Desert Island, bike the carriage "
                    "roads, and time a Cadillac summit sunrise."
                ),
                itinerary=[
                    "Day 1 — Ocean Path: Sand Beach to Otter Cliff, Thunder Hole at mid-tide",
                    "Day 2 — Carriage-road bike loop, Jordan Pond popovers",
                    "Day 3 — Cadillac sunrise (vehicle reservation!), Bass Harbor Head Light at dusk",
                ],
                targets=[
                    PlanTarget("Blackwoods Campground", "campground", None, "Closest to Bar Harbor and Ocean Drive"),
                    PlanTarget("Seawall Campground", "campground", None, "The mellow 'quiet side' alternative"),
                ],
            ),
            Trip(
                title="Schoodic Escape",
                style="family",
                nights=2,
                best_months="Jul–Sep",
                summary=(
                    "The mainland peninsula: same granite-and-surf drama at a tenth "
                    "of the crowds, with a bike loop made for kids."
                ),
                itinerary=[
                    "Day 1 — Schoodic Loop Road, tidepooling at Schoodic Point",
                    "Day 2 — Bike the peninsula paths, lobster roll in Winter Harbor",
                    "Day 3 — Ferry or drive around to Bar Harbor for one busy-side day",
                ],
                targets=[
                    PlanTarget("Schoodic Woods Campground", "campground", None, "Modern sites with hookups on the peninsula"),
                ],
            ),
        ],
        activities=[
            Activity("Cadillac Mountain sunrise", "scenic", "First light in the U.S. (Oct–Mar) — vehicle reservations via recreation.gov."),
            Activity("Carriage roads by bike", "scenic", "45 car-free miles of Rockefeller's crushed-stone roads and granite bridges."),
            Activity("Beehive Trail", "hike", "Iron-rung ladder scramble above Sand Beach — short, steep, unforgettable."),
            Activity("Thunder Hole", "water", "Time it ~2 hours before high tide for the boom."),
            Activity("Bar Harbor evening", "town", "Ice cream on the green and the Shore Path at dusk."),
        ],
        eats=[
            Eat("Jordan Pond House", "In the park", "Popovers and tea on the lawn — a 130-year tradition with a mountain view."),
            Eat("Beal's Lobster Pier", "Southwest Harbor", "Pick-your-lobster dockside dining on the quiet side."),
            Eat("Side Street Cafe", "Bar Harbor", "The reliable lobster-roll-and-blueberry-ale downtown spot."),
            Eat("Mount Dessert Bakery", "Bar Harbor", "Early coffee and pastries before a sunrise start."),
        ],
        amenities=Amenities(
            showers=["No showers in park campgrounds — Mount Desert Campground & private operators sell showers", "Bar Harbor's aquatic center offers day passes"],
            laundry=["Bar Harbor Laundromat on Cottage Street"],
            groceries=["Hannaford supermarket in Bar Harbor; Sawyer's Market in Southwest Harbor"],
            connectivity="Good on most of Mount Desert Island; spotty on Schoodic and Isle au Haut.",
            heads_up="Cadillac sunrise now requires a timed vehicle reservation — it sells out fast in foliage season.",
        ),
    ),
)


def all_parks() -> list[dict]:
    return [p.summary() for p in PARKS]


def get_park(slug: str) -> Optional[dict]:
    for p in PARKS:
        if p.slug == slug:
            return p.full()
    return None
