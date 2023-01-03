import pytz
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import bid_forms, comment_forms, create_listing_forms
from .models import Auction_Listing, Bid, Comment, User


def index(request):
    return render(
        request,
        "auctions/index.html",
        {"listings": Auction_Listing.objects.exclude(winner__isnull=False)},
    )


def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(
                request,
                "auctions/login.html",
                {"message": "Invalid username and/or password."},
            )
    else:
        return render(request, "auctions/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        timezone = request.POST["timezone"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(
                request, "auctions/register.html", {"message": "Passwords must match."}
            )

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)  # type: ignore
            tz = pytz.timezone(timezone)
            user.timezone = tz
            user.save()
        except IntegrityError:
            return render(
                request,
                "auctions/register.html",
                {"message": "Username already taken."},
            )
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        timezones = pytz.common_timezones
        return render(request, "auctions/register.html", {"timezones": timezones})


@login_required(redirect_field_name="", login_url="login")
def create_listing(request):
    if request.method == "POST":
        form = create_listing_forms(request.POST, request.FILES)
        if form.is_valid():
            # file is saved
            new_listing = form.save(commit=False)
            new_listing.user = request.user
            new_listing.save()

            return redirect("index")
    else:
        form = create_listing_forms()
    return render(request, "auctions/createlisting.html", {"form": form})


def active_listing(request, id):
    user = request.user
    listing = Auction_Listing.objects.get(id=id)
    bids = bid_forms()
    comments = Comment.objects.all().filter(auction_id=id)
    comment_form = comment_forms()
    watchlist_number = listing.watchers.count()  # type: ignore
    if not user.is_authenticated:
        return render(
            request,
            "auctions/listing.html",
            {
                "listing": listing,
                "comments": comments,
                "watchlist_number": watchlist_number,
            },
        )

    else:
        if request.method == "POST" and user.is_authenticated:
            if "bidding_form" in request.POST:
                bidding_form = bid_forms(request.POST)
                if bidding_form.is_valid() and (
                    bidding_form.cleaned_data.get("new_bid")
                    < listing.item_initial_price
                ):
                    messages.warning(
                        request, "New bid amount must be higher than the posted one."
                    )
                    return redirect("listing", id=id)

                else:
                    new_bidding_form = bidding_form.save(commit=False)
                    new_bidding_form.auction_id = listing
                    new_bidding_form.user = user
                    # Updates the listings price to the new bid
                    Auction_Listing.objects.filter(id=id).update(
                        item_initial_price=new_bidding_form.new_bid
                    )
                    new_bidding_form.save()
                    return redirect("listing", id=id)

            comment_form = comment_forms(request.POST)
            if comment_form.is_valid() and "comment_form" in request.POST:
                new_comment_form = comment_form.save(commit=False)
                new_comment_form.auction_id = listing
                new_comment_form.user = user
                new_comment_form.save()
                comment_form = comment_forms()
                return redirect("listing", id=id)

            if "watchlist_button" in request.POST:
                watchlist_number = listing.watchers.count()  # type: ignore
                if (
                    user
                    == listing.watchers.filter(username__exact=user.username).first()  # type: ignore
                ):
                    listing.watchers.remove(user)  # type: ignore
                    return redirect("listing", id=id)
                else:
                    user.watchlist_item.add(listing)
                    return redirect("listing", id=id)

            if "delete_button" in request.POST:
                if user.id == listing.user.id:  # type: ignore
                    # TODO: Set a confirmation toast for this
                    listing.winner = Bid.objects.filter(auction_id=id).last().user
                    listing.save()
                    return redirect("closedauctions")
                else:
                    # TODO: Set a toast for this
                    return redirect("index")

    return render(
        request,
        "auctions/listing.html",
        {
            "listing": listing,
            "bidding_form": bids,
            "comment_form": comment_form,
            "comments": comments,
            "watchlist_number": watchlist_number,
        },
    )


@login_required(redirect_field_name="", login_url="login")
def watchlist(request, id):
    # Button to remove the watchlisted item from the user's watchlist
    user = request.user
    if "remove_button" in request.POST:
        print(user.watchlist_item.get(item_title=request.POST[item.item_title]))

    else:
        return render(
            request,
            "auctions/watchlist.html",
            {"watchlisted_items": Auction_Listing.objects.filter(watchers=id)},
        )


def categories(request, item_category):
    return render(
        request,
        "auctions/categories.html",
        {
            "categories": Auction_Listing.objects.all().filter(
                item_category=item_category
            )
        },
    )


def closed_auctions(request):
    return render(
        request,
        "auctions/closedauctions.html",
        {"listings": Auction_Listing.objects.exclude(winner__isnull=True)},
    )
