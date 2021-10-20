import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    portfolio = []
    # get the user details from db
    #portfolio = db.execute("SELECT * FROM users where username = ?", session.get("user_id"))
    user = db.execute("SELECT * FROM users WHERE id = ?", session.get("user_id"))
    pt = db.execute("SELECT symbol, name, SUM(shares) as shares FROM portfolio WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", session.get("user_id"))
    for row in pt:
        tmp = {}
        qt = lookup(row["symbol"])
        totalPrice = (row["shares"] * qt["price"])
        tmp["symbol"] = row["symbol"]
        tmp["name"] = qt["name"]
        tmp["shares"] = row["shares"]
        tmp["price"] = qt["price"]
        tmp["total"] = totalPrice
        portfolio.append(tmp)

    total = 0

    for row in portfolio:
        total += row["total"]

    total += user[0]["cash"]

    return render_template("index.html", user=user, portfolio=portfolio, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("Must provide a stock symbol", 400)
        elif not request.form.get("shares"):
            return apology("Must provide number of shares", 400)
        else:
            try:
                val = int(request.form.get("shares"))
                if val < 0:  # if not a positive int return apology
                    return apology("Shares must be a positive integer", 400)
            except ValueError:
                    return apology("Shares is not an integer", 400)

            qt = lookup(request.form.get("symbol"))
            if not qt:
                return apology("Stock symbol does not exist", 400)

            userRec = db.execute("SELECT * FROM users WHERE id = ?", session.get("user_id"))
            #portfolio =  db.execute("SELECT * FROM portfolio WHERE user_id = ? and symbol = ?", session.get("user_id"), request.form.get("symbol"))
            # check total cost $
            shares = float(request.form.get("shares"))
            totalCost = (qt["price"] * shares)

            if totalCost > userRec[0]["cash"]:
                return apology("You do not have enough cash to purchase", 400)
            else:
                cashLeft = userRec[0]["cash"] - totalCost
                db.execute("INSERT INTO portfolio (user_id, symbol, name, shares, purchase_price, date_purchased) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", session.get("user_id"), qt["symbol"], qt["name"], shares, qt["price"])
                # update the user cash
                db.execute("UPDATE users set cash = ? where id = ?", cashLeft, session.get("user_id"))

            # redirect to (/)
            flash("Bought!")
            return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    pt = db.execute("SELECT * from portfolio where user_id = ? order by date_purchased DESC", session.get("user_id"))

    return render_template("history.html", portfolio=pt)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        flash(request.form.get("username") + " logged In!")
        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide a stock symbol", 400)
        else:
            """Get stock quote."""
            qt = lookup(request.form.get("symbol"))
            if qt:
                return render_template("quoted.html", qt=qt)
            else:
                return apology("Stock symbol does not exist", 400)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username", 400)

        # check if user name is already taken
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) > 0:
             return apology("Username already exists", 400)
        # Ensure password was submitted
        elif not request.form.get("password") or not request.form.get("confirmation"):
            return apology("must provide passwords", 400)
        # Ensure the password again matches the password
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)
        else:
            # get password hash
            hashedPassword = generate_password_hash(request.form.get("password"))
            # if all passed, insert user into database and redirect to index.html?
            id = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), hashedPassword)
            # Remember which user has logged in
            session["user_id"] = id
            # Redirect user to home page with registered message
            flash("Registered!")
            return redirect("/")
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    pt = db.execute("SELECT symbol, name, SUM(shares) as shares FROM portfolio WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", session.get("user_id"))
    userRec = db.execute("SELECT * FROM users WHERE id = ?", session.get("user_id"))
    portfolio = {}
    for p in pt:
        qt = lookup(p["symbol"])
        portfolio[p["symbol"]] = {"price":qt["price"], "shares":p["shares"], "name":qt["name"]}

    if request.method == "POST":
        """Sell shares of stock"""
        if not request.form.get("symbol"):
            return apology("Must select a stock symbol to sell", 400)
        elif not request.form.get("shares"):
            return apology("Must provide number of shares", 400)
        else:
            try:
                val = int(request.form.get("shares"))
                if val < 0:  # if not a positive int return apology
                    return apology("Shares must be a positive integer", 400)
            except ValueError:
                    return apology("Shares is not an integer", 400)

            curr_price = portfolio[request.form.get("symbol")]["price"]
            form_shares = float(request.form.get("shares"))
            form_symbol = request.form.get("symbol")
            qt_name = portfolio[form_symbol]["name"]
            qt_price = portfolio[form_symbol]["price"]

            if portfolio[form_symbol]["shares"] < form_shares:
                return apology("Shares entered is higher than what is owned", 400)

            amountSold = (form_shares * curr_price)
            # insert a negative number of shares into portfolio table
            cashAfter = userRec[0]["cash"] + amountSold
            sharesSubtract = (0 - form_shares)
            db.execute("INSERT INTO portfolio (user_id, symbol, name, shares, purchase_price, date_purchased) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", session.get("user_id"), form_symbol, qt_name, sharesSubtract, qt_price)
            # update the user cash
            db.execute("UPDATE users set cash = ? where id = ?", cashAfter, session.get("user_id"))

            # redirect to (/)
            flash("Sold!")
            return redirect("/")
    else:
        return render_template("sell.html", portfolio=portfolio, user=userRec)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
