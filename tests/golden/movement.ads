-- Generated from DRAKON and explicit ada metadata. DO NOT EDIT.
package Movement with SPARK_Mode => On is
   type Quantity is range -2000000 .. 2000000;
   subtype Positive_Amount is Quantity range 1 .. 1000000;

   procedure Balanced_Movement (Amount : in Positive_Amount; Source : out Quantity; Destination : out Quantity)
     with Post => Source = -Amount and then Destination = Amount and then Source + Destination = 0;
end Movement;
