# steelbooksatbestbuy

```
if keeping from backup:
    cp /var/services/homes/jace/steelbooksatbestbuy/sqlite_db/db.sqlite3 /var/services/homes/jace/db.sqlite3
fi
docker rm -f steelbooksatbestbuy_bot steelbooksatbestbuy_poll_bestbuy steelbooksatbestbuy_website \
 && docker system prune -a -f
cd ~/
rm -r steelbooksatbestbuy
git clone http://github.com/modernNeo/steelbooksatbestbuy.git
cp ~/steelbooksatbestbuy_dockerized.env ~/steelbooksatbestbuy/.
mkdir -p ~/steelbooksatbestbuy/sqlite_db
if keeping from backup:
    cp /var/services/homes/jace/db.sqlite3 /var/services/homes/jace/steelbooksatbestbuy/sqlite_db/db.sqlite3
fi
cd ~/steelbooksatbestbuy
docker-compose -f docker-compose.yml up --force-recreate -d #synology
docker compose -f docker-compose.yml up --force-recreate -d #debian
docker exec -it steelbooksatbestbuy_website python manage.py migrate
docker exec -it steelbooksatbestbuy_website python manage.py createsuperuser
```