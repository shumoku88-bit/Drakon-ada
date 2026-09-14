with Ada.Text_IO;
with Movement;

procedure Movement_Test is
   use Movement;
   Source, Destination : Quantity;
begin
   -- Exhaust the finite input subtype, including both endpoints.
   for Amount in Positive_Amount loop
      Balanced_Movement (Amount, Source, Destination);
      if Source /= -Amount or else Destination /= Amount
        or else Source + Destination /= 0
      then
         raise Program_Error with "Unbalanced movement";
      end if;
   end loop;
   Ada.Text_IO.Put_Line ("PASS: all 1000000 valid amounts");
end Movement_Test;
