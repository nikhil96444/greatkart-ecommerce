
from django.shortcuts import render, redirect
from carts.models import Cart, CartItem
from .forms import OrderForm
from .models import Payment, Order, OrderProduct
from django.contrib.auth.decorators import login_required
from store.models import Product
from django.http import JsonResponse, HttpResponse
import datetime
import json
from django.core.mail import EmailMessage
from django.template.loader import render_to_string 
from store.models import Product


def payments(request):
    body = json.loads(request.body)
    order = Order.objects.get(user=request.user, is_ordered=False, order_number=body['orderID'])

    # Store transaction details inside Payment model
    payment = Payment(
        user = request.user,
        payment_id = body['transID'],
        payment_method = body['payment_method'],
        amount_paid = order.order_total,
        status = body['status'],
    )
    payment.save()

    order.payment = payment
    order.is_ordered = True
    order.save()

    # Move the cart items to Order Product table
    cart_items = CartItem.objects.filter(user=request.user)

    for item in cart_items:
        orderproduct = OrderProduct()
        orderproduct.order_id = order.id
        orderproduct.payment = payment
        orderproduct.user_id = request.user.id
        orderproduct.product_id = item.product_id
        orderproduct.quantity = item.quantity
        orderproduct.product_price = item.product.price
        orderproduct.ordered = True
        orderproduct.save()

        cart_item = CartItem.objects.get(id=item.id)
        product_variation = cart_item.variations.all()
        orderproduct = OrderProduct.objects.get(id=orderproduct.id)
        orderproduct.variations.set(product_variation)
        orderproduct.save()


        # Reduce the quantity of the sold products
        product = Product.objects.get(id=item.product_id)
        product.stock -= item.quantity
        product.save()

    # Clear cart
    CartItem.objects.filter(user=request.user).delete()

    # Send order recieved email to customer
    mail_subject = 'Thank you for your order!'
    message = render_to_string('orders/order_recieved_email.html', {
        'user': request.user,
        'order': order,
    })
    to_email = request.user.email
    send_email = EmailMessage(mail_subject, message, to=[to_email])
    send_email.send()

    # Send order number and transaction id back to sendData method via JsonResponse
    data = {
        'order_number': order.order_number,
        'transID': payment.payment_id,
    }
    return JsonResponse(data)


@login_required(login_url='login')
def place_order(request, total=0, quantity=0):

    print('--------------------------->',)
    current_user = request.user

    # Cart count <= 0, redirect to store.
    cart_items = CartItem.objects.filter(user=current_user)

    cart_count = cart_items.count()
    if cart_count <= 0:
        return redirect('store')

    grand_total = 0
    tax = 0
    
    for cart_item in cart_items:
        total += (cart_item.product.price*cart_item.quantity)
        quantity += cart_item.quantity
    
    tax = (2 * total)/100
    grand_total = total + tax

    order_id = 100
    
    
    if request.method == 'POST':
        order_obj = Order(
            order_id = 100,
            user = request.user,
            first_name = request.POST.get('first_name'),
            last_name = request.POST.get('last_name'),
            phone = request.POST.get('phone'),
            email = request.POST.get('email'),
            address_line_1 = request.POST.get('address_line_1'),
            address_line_2 = request.POST.get('address_line_2'),
            pin_code = 12345,
            state = request.POST.get('state'),
            city = request.POST.get('city'),
            country = request.POST.get('country'),
            order_note = request.POST.get('order_note'),
            order_total = grand_total,
            tax = tax,
            ip = request.META.get('Remote_ADDR')
            )
        yr = int(datetime.date.today().strftime('%Y'))
        dt = int(datetime.date.today().strftime('%d'))
        mt = int(datetime.date.today().strftime('%m'))
        d = datetime.date(yr,mt,dt)
        current_date = d.strftime("%Y%m%d")#20210305
        order_number = current_date + str(order_id)
        order_obj.order_number = order_number
        order_obj.save()



        context = {
            'order_obj':order_obj,
            'cart_items':cart_items,
            'total': total,
            'tax': tax,
            'grand_total': grand_total,
            'order_number': order_number,

        }



        
            # Generate Order Number
        # yr = int(datetime.date.today().strftime('%Y'))
        # dt = int(datetime.date.today().strftime('%d'))
        # mt = int(datetime.date.today().strftime('%m'))
        # d = datetime.date(yr,mt,dt)
        # current_date = d.strftime("%Y%m%d") #20210305
        # order_number = current_date + str(id)
        # order_obj.order_number = order_number
        # data.save()
        return render(request, 'orders/payments.html', context)
    else:
        return redirect('checkout')

    
def order_complete(request):
    order_number = request.GET.get('order_number')
    transID = request.GET.get('payment_id')

    try:
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)

        subtotal = 0
        for i in ordered_products:
            subtotal += i.product_price * i.quantity

        payment = Payment.objects.get(payment_id=transID)

        context = {
            'order': order,
            'ordered_products': ordered_products,
            'order_number': order.order_number,
            'transID': payment.payment_id,
            'payment': payment,
            'subtotal': subtotal,
        }
        return render(request, 'orders/order_complete.html', context)
    except (Payment.DoesNotExist, Order.DoesNotExist):
        return redirect('home')

    