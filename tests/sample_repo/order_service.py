from notification import send_notification
from payment import process_payment
from database import save_order


class OrderService:

    def create_order(self, customer, product):
        save_order(customer, product)
        process_payment(customer)
        send_notification(customer)


def cancel_order(order_id):
    print("Cancelling order")
