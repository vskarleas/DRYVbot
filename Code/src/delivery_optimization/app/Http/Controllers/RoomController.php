<?php

namespace App\Http\Controllers;

use App\Models\Room;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class RoomController extends Controller
{
    public function index(): Response
    {
        $rooms = Room::orderBy('name')->paginate(20);
        return Inertia::render('rooms/index', ['rooms' => $rooms]);
    }

    public function store(Request $request): RedirectResponse
    {
        $request->validate([
            'name' => ['required', 'string', 'max:255'],
            'code' => ['required', 'string', 'max:50', 'unique:rooms'],
            'building' => ['nullable', 'string', 'max:100'],
            'floor' => ['nullable', 'string', 'max:50'],
            'description' => ['nullable', 'string'],
        ]);

        Room::create($request->all());

        return back()->with('success', 'Salle ajout\u00e9e.');
    }

    public function update(Request $request, Room $room): RedirectResponse
    {
        $request->validate([
            'name' => ['required', 'string', 'max:255'],
            'code' => ['required', 'string', 'max:50', 'unique:rooms,code,' . $room->id],
            'building' => ['nullable', 'string', 'max:100'],
            'floor' => ['nullable', 'string', 'max:50'],
            'description' => ['nullable', 'string'],
            'is_active' => ['boolean'],
        ]);

        $room->update($request->all());

        return back()->with('success', 'Salle mise \u00e0 jour.');
    }

    public function destroy(Room $room): RedirectResponse
    {
        $room->delete();
        return back()->with('success', 'Salle supprim\u00e9e.');
    }
}