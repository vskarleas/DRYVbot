<?php

namespace App\Http\Controllers;

use App\Enums\OrderStatus;
use App\Events\OrderCreated;
use App\Events\OrderStatusUpdated;
use App\Http\Requests\CancelOrderRequest;
use App\Http\Requests\ImportOrderRequest;
use App\Http\Requests\StoreOrderRequest;
use App\Imports\OrderImport;
use App\Models\Medication;
use App\Models\Order;
use App\Models\Room;
use App\Services\DeliveryPlannerService;
use App\Services\DtOutboundQueueService;
use App\Services\OcrService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Inertia\Inertia;
use Inertia\Response;
use Maatwebsite\Excel\Facades\Excel;

class OrderController extends Controller
{
    public function __construct(
        private readonly DeliveryPlannerService $planner,
        private readonly OcrService $ocr,
        private readonly DtOutboundQueueService $dtOutboundQueue,
    ) {}

    public function index(Request $request): Response
    {
        $query = Order::with(['departureRoom', 'arrivalRoom', 'creator'])->latest();

        if ($request->filled('status')) {
            $query->where('status', $request->string('status'));
        }
        if ($request->filled('departure_room_id')) {
            $query->where('departure_room_id', $request->integer('departure_room_id'));
        }
        $orders = $query->paginate(20)->withQueryString();
        $rooms = Room::where('is_active', true)->orderBy('name')->get(['id', 'name', 'code']);
        $medications = Medication::where('is_active', true)->orderBy('name')->get(['id', 'name', 'code']);

        return Inertia::render('orders/index', [
            'orders' => $orders,
            'rooms' => $rooms,
            'medications' => $medications,
            'filters' => $request->only(['status', 'departure_room_id']),
        ]);
    }

    public function create(): Response
    {
        $rooms = Room::where('is_active', true)->orderBy('name')->get(['id', 'name', 'code']);
        $medications = Medication::where('is_active', true)->orderBy('name')->get(['id', 'name', 'code']);

        return Inertia::render('orders/create', [
            'rooms' => $rooms,
            'medications' => $medications,
        ]);
    }

    public function store(StoreOrderRequest $request): RedirectResponse
    {
        $data = $request->validated();
        $medicationNames = Medication::whereIn('id', $data['medication_ids'])->orderBy('name')->pluck('name')->all();

        $data['created_by'] = $request->user()->id;
        $data['content'] = implode(', ', $medicationNames);
        $data['is_critical'] = (bool) ($data['is_critical'] ?? false);
        unset($data['medication_ids']);

        $order = Order::create($data);
        $order->refresh();
        $order->load(['arrivalRoom']);

        OrderCreated::dispatch($order);

        return redirect()->route('orders.index')
            ->with('success', "Commission {$order->reference} créée avec succès.");
    }

    public function initializePlanning(): RedirectResponse
    {
        $activePlan = $this->planner->getActivePlan();

        if ($activePlan !== null && $this->planner->hasRemainingOrders($activePlan)) {
            return back()->with('error', 'Un lot de livraisons est déjà en cours.');
        }

        $plan = $this->planner->initializeBatchPlan(now(), DeliveryPlannerService::BATCH_WINDOW_MINUTES);

        \Log::info('Batch plan initialized', ['plan' => $plan]);
        if ($plan === null) {
            return back()->with('error', 'Aucune commande en attente dans la fenêtre de 15 minutes autour de maintenant.');
        }

        $startRoom = $this->planner->getStartRoom();

        if ($startRoom === null) {
            return back()->with('error', 'Salle de depart introuvable (code: salle_reception).');
        }

        $this->dtOutboundQueue->push([
            'type' => 'room_command',
            'room' => $startRoom->code,
        ]);

        \Log::info('Batch initialization queued immediate start-room command', [
            'plan_id' => $plan->id,
            'room' => $startRoom->code,
            'last_status' => Cache::get('dt:last_status_payload'),
            'process' => 'orders.initializePlanning',
        ]);

        return back()->with('success', 'Planification initialisée. Les commissions critiques sont exécutées en premier, puis les non critiques.');
    }

    public function show(Order $order): Response
    {
        $order->load(['departureRoom', 'arrivalRoom', 'creator', 'cancelledBy']);

        return Inertia::render('orders/show', [
            'order' => $order,
        ]);
    }

    public function deliver(Order $order): RedirectResponse
    {
        \Log::info('Marking order as delivered', ['order' => $order]);
        abort_unless($order->status === OrderStatus::InTransit, 403);

        $order->update([
            'status' => OrderStatus::Delivered,
            'delivered_at' => now(),
        ]);

        OrderStatusUpdated::dispatch($order->fresh());
        $this->planner->plan($order->arrivalRoom);

        return back()->with('success', "Commission {$order->reference} marquée comme livrée.");
    }

    public function cancel(CancelOrderRequest $request, Order $order): RedirectResponse
    {
        abort_unless(in_array($order->status, [OrderStatus::Pending, OrderStatus::InTransit]), 403);

        $order->update([
            'status' => OrderStatus::Cancelled,
            'cancelled_by' => $request->user()->id,
            'cancellation_reason' => $request->validated('reason'),
            'cancelled_at' => now(),
        ]);

        OrderStatusUpdated::dispatch($order->fresh());

        return back()->with('success', "Commission {$order->reference} annulée.");
    }

    public function dispatchRemoteSocket(Order $order): RedirectResponse
    {
        $order->loadMissing('arrivalRoom');

        if ($order->arrivalRoom === null || trim((string) $order->arrivalRoom->code) === '') {
            return back()->with('error', "Commission {$order->reference} sans salle d'arrivée.");
        }

        $this->dtOutboundQueue->push([
            'type' => 'room_command',
            'room' => $order->arrivalRoom->code,
        ]);

        // declencher le 1er planificateur a partir du point de livraison de la commande de la derniere commande sinon de la pharmacie

        return back()->with('success', "Commande DT pour {$order->reference} envoyée en file.");
    }

    public function importExcel(ImportOrderRequest $request): RedirectResponse
    {
        Excel::import(
            new OrderImport($request->user()->id),
            $request->file('file')
        );

        return redirect()->route('orders.index')->with('success', 'Commissions importées.');
    }

    public function importOcr(Request $request): JsonResponse
    {
        $request->validate(['file' => ['required', 'file', 'mimes:pdf,png,jpg,jpeg', 'max:10240']]);

        $text = $this->ocr->extractText($request->file('file'));
        $parsed = $this->ocr->parseOrderData($text);

        return response()->json(['extracted' => $parsed, 'raw_text' => $text]);
    }
}
